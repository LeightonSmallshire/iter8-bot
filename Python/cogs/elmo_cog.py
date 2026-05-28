import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import discord
import logfire
from discord.ext import commands
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from .agent_elmo.deps import AgentDeps
from .agent_elmo.graph import create_agent_graph
from .agent_elmo.memory.store import AgentMemoryStore
from .agent_elmo.sandbox.manager import SandboxManager
from .agent_elmo.util import easy_send

# --- Configuration ---
TRUSTED_USERS: set[int] = {1416017385596653649, 1326156803108503566}

load_dotenv("data/.env")
load_dotenv()

logfire.configure(console=logfire.ConsoleOptions(min_log_level="debug"))

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

        channel_id: int | None = getattr(message.channel, "id", None)
        if channel_id is None or channel_id not in self.allowed_channels:
            return

        is_mentioned = self.bot.user is not None and self.bot.user.mentioned_in(message)
        is_reply = False
        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and self.bot.user:
                is_reply = resolved.author.id == self.bot.user.id

        state = self.channel_states.setdefault(channel_id, ChannelState())

        if is_mentioned or is_reply:
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

        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            logfire.warn("unsupported_channel_type", channel_id=channel_id)
            return

        # Find the last bot message in this channel
        last_bot_msg = None
        async for msg in channel.history(limit=100):
            if self.bot.user and msg.author.id == self.bot.user.id:
                last_bot_msg = msg
                break

        # Collect user messages since last bot message
        kwargs: dict[str, Any] = {"limit": 200}
        if last_bot_msg is not None:
            kwargs["after"] = last_bot_msg.created_at

        new_messages: list[HumanMessage] = []
        async for msg in channel.history(**kwargs):
            if msg.author.bot:
                continue
            new_messages.append(HumanMessage(content=msg.clean_content))

        if not new_messages:
            logfire.info("no_new_messages", channel_id=channel_id)
            return

        # history() returns newest first, reverse to chronological
        new_messages.reverse()

        deps = AgentDeps(
            bot=self.bot,
            sandbox_manager=sandbox_manager,
        )

        state = {
            "messages": new_messages,
            "channel_id": channel_id,
        }

        config: RunnableConfig = {
            "configurable": {
                "thread_id": str(channel_id),
                "deps": deps,
            }
        }

        async with channel.typing():
            try:
                final_state = await graph.ainvoke(state, config=config)
                last_msg = final_state["messages"][-1]
                if isinstance(last_msg, AIMessage):
                    content = last_msg.content
                    if isinstance(content, list):
                        text_content = " ".join(
                            block["text"]
                            for block in content
                            if isinstance(block, dict) and "text" in block
                        )
                        await easy_send(channel, text_content)
                    else:
                        await easy_send(channel, str(content))
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
