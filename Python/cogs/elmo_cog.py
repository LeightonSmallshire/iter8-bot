import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import discord
import logfire
from discord.ext import commands
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from .agent_elmo.deps import AgentDeps
from .agent_elmo.graph import create_agent_graph
from .agent_elmo.memory.store import AgentMemoryStore
from .agent_elmo.sandbox.manager import SandboxManager
from .agent_elmo.util import easy_send


def _extract_response_content(messages: list) -> str | None:
    """Return the final response content from the agent's message list.

    The agent must call respond() to deliver its answer — plain AIMessage
    text is internal reasoning and MUST NOT reach the user.
    """
    respond_ids: set[str] = set()
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc.get("name") == "respond":
                    respond_ids.add(tc["id"])

    for msg in reversed(messages):
        if isinstance(msg, ToolMessage) and msg.tool_call_id in respond_ids:
            return str(msg.content)
    return None


# --- Configuration ---
TRUSTED_USERS: set[int] = {1416017385596653649, 1326156803108503566}

load_dotenv("data/.env")
load_dotenv()

# Global agent state
memory_store = AgentMemoryStore()
sandbox_manager = SandboxManager()
_agent_graph = create_agent_graph()
graph: Any = None


@dataclass
class ChannelState:
    event: asyncio.Event = field(default_factory=asyncio.Event)
    should_run: bool = False
    worker_task: asyncio.Task[Any] | None = None
    last_activity: float = 0.0


class AgentCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.allowed_channels: set[int] = {1498977340821209198, 1432698704191815680, 1439936991096737804}
        self.channel_states: dict[int, ChannelState] = {}
        self.SILENCE_DELAY: float = 3.0

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        channel_id: int | None = getattr(message.channel, "id", None)
        if channel_id is None:
            return
        if not is_dm and channel_id not in self.allowed_channels:
            return

        is_mentioned = self.bot.user is not None and self.bot.user.mentioned_in(message)
        is_reply = False
        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and self.bot.user:
                is_reply = resolved.author.id == self.bot.user.id

        state = self.channel_states.setdefault(channel_id, ChannelState())

        if is_dm or is_mentioned or is_reply:
            state.should_run = True
            state.last_activity = time.monotonic()
            state.event.set()
            self._start_worker_if_needed(channel_id)
        elif state.should_run:
            state.last_activity = time.monotonic()
            state.event.set()

    def _start_worker_if_needed(self, channel_id: int) -> None:
        state = self.channel_states[channel_id]
        if state.worker_task is None or state.worker_task.done():
            state.worker_task = asyncio.create_task(self._worker(channel_id))

    async def _worker(self, channel_id: int) -> None:
        state = self.channel_states[channel_id]
        try:
            while True:
                await state.event.wait()
                state.event.clear()

                # Wait for silence — reset timer if new activity arrives
                while True:
                    deadline = state.last_activity + self.SILENCE_DELAY
                    sleep_for = deadline - time.monotonic()
                    if sleep_for <= 0:
                        break
                    try:
                        await asyncio.wait_for(state.event.wait(), timeout=sleep_for)
                        state.event.clear()
                    except TimeoutError:
                        break

                if state.should_run:
                    state.should_run = False
                    try:
                        await self._do_work(channel_id)
                    except Exception:
                        logfire.exception("do_work_failed", channel_id=channel_id)
        except asyncio.CancelledError:
            pass
        except Exception:
            logfire.exception("worker_crashed", channel_id=channel_id)
        finally:
            self.channel_states.pop(channel_id, None)

    @logfire.instrument
    async def _do_work(self, channel_id: int) -> None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            logfire.warn("channel_not_found", channel_id=channel_id)
            return

        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
            logfire.warn("unsupported_channel_type", channel_id=channel_id)
            return

        # Find the last bot message in this channel
        last_bot_msg = None
        async for msg in channel.history(limit=200):
            if self.bot.user and msg.author.id == self.bot.user.id:
                last_bot_msg = msg
                break

        # Collect user messages since last bot message.
        # Using the Message object for `after` gives snowflake-precision ordering
        # (vs second-precision with .created_at), and setting id=str(msg.id)
        # lets add_messages deduplicate by Discord message ID instead of always appending.
        kwargs: dict[str, Any] = {"limit": 200}
        if last_bot_msg is not None:
            kwargs["after"] = last_bot_msg

        new_messages: list[HumanMessage] = []
        async for msg in channel.history(**kwargs):
            if msg.author.bot:
                continue
            new_messages.append(HumanMessage(content=msg.clean_content, id=str(msg.id)))

        if not new_messages:
            logfire.info("no_new_messages", channel_id=channel_id)
            return

        # history() returns newest first, reverse to chronological
        new_messages.reverse()

        deps = AgentDeps(
            bot=self.bot,
            sandbox_manager=sandbox_manager,
        )

        config: RunnableConfig = {
            "configurable": {
                "thread_id": str(channel_id),
                "deps": deps,
            }
        }

        # Load existing checkpoint messages so Logfire captures the full
        # message history in the trace input (instead of only new_messages,
        # which makes the trace look like the latest message is duplicated).
        all_messages: list = list(new_messages)
        if graph:
            try:
                checkpoint = await graph.aget_state(config)
                if checkpoint and checkpoint.values.get("messages"):
                    all_messages = [*checkpoint.values["messages"], *new_messages]
            except Exception:
                pass

        state = {
            "messages": all_messages,
            "channel_id": channel_id,
        }

        async with channel.typing():
            try:
                final_state = await graph.ainvoke(state, config=config)
                content = _extract_response_content(final_state["messages"])
                if content:
                    await easy_send(channel, content)
                else:
                    await channel.send("System: Agent failed to return a valid response.")
            except Exception as e:
                logfire.error("agent_run_error", error=e)
                await channel.send(f"System: Agent error — {type(e).__name__}")

    async def cog_unload(self) -> None:
        for state in self.channel_states.values():
            if state.worker_task and not state.worker_task.done():
                state.worker_task.cancel()
        self.channel_states.clear()


async def setup(bot: commands.Bot) -> None:
    memory_store.cleanup_old_checkpoints()
    global graph
    checkpointer = await memory_store.get_checkpointer()
    graph = _agent_graph.compile(checkpointer=checkpointer)
    await bot.add_cog(AgentCog(bot=bot))
