import asyncio
import contextlib
import os
import logfire
from typing import Any

import discord
from discord.ext import commands
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from .agent_elmo.graph import create_agent_graph
from .agent_elmo.deps import AgentDeps
from .agent_elmo.sandbox.manager import SandboxManager
from .agent_elmo.memory.store import AgentMemoryStore
from .agent_elmo.util import easy_send

# --- Configuration ---
TRUSTED_USERS: set[int] = {1416017385596653649, 1326156803108503566}

load_dotenv("data/.env")
load_dotenv()

logfire.configure(console=logfire.ConsoleOptions(min_log_level="debug"))

# Global agent state
memory_store = AgentMemoryStore()
sandbox_manager = SandboxManager()
graph = create_agent_graph().compile(checkpointer=memory_store.get_checkpointer())

class AgentCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.allowed_channels: set[int] = {1498977340821209198, 1432698704191815680, 1439936991096737804}
        self.silence_tasks: dict[int, asyncio.Task[Any]] = {}
        self.run_tasks: dict[int, asyncio.Task[Any]] = {}
        self.pending_messages: dict[int, discord.Message] = {}
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

        if is_mentioned or is_reply:
            cid = channel_id
            self.pending_messages[cid] = message
            if cid in self.silence_tasks:
                self.silence_tasks[cid].cancel()

            async def wait_for_silence() -> None:
                try:
                    await asyncio.sleep(self.SILENCE_DELAY)
                    if cid in self.pending_messages:
                        msg = self.pending_messages.pop(cid)
                        if cid in self.run_tasks:
                            with contextlib.suppress(BaseException):
                                await self.run_tasks[cid]
                        task = asyncio.create_task(self.run_agent(msg.channel))
                        self.run_tasks[cid] = task
                        try:
                            await task
                        finally:
                            if cid in self.run_tasks:
                                del self.run_tasks[cid]
                except asyncio.CancelledError:
                    pass
                finally:
                    if cid in self.silence_tasks and self.silence_tasks[cid].done():
                        del self.silence_tasks[cid]

            self.silence_tasks[cid] = asyncio.create_task(wait_for_silence())

    @logfire.instrument
    async def run_agent(self, channel: discord.abc.Messageable) -> None:
        cid = getattr(channel, "id", 0)

        async with channel.typing():
            # 1. Prepare Dependencies
            deps = AgentDeps(
                bot=self.bot,
                sandbox_manager=sandbox_manager,
                mem0_client=None, # Add if MEM0_API_KEY is used
            )
            
            # 2. Prepare Input state
            # We bootstrap current messages into LangChain format if no history exists
            # But LangGraph checkpointer handles history automatically if we provide thread_id.
            # We only need to provide the latest user message.
            
            # Find the last message that triggered the run
            # Since pending_messages was popped, we need to fetch it or pass it.
            # Actually, we can just fetch the last message from the channel.
            async for msg in channel.history(limit=1):
                user_prompt = msg.clean_content
                break
            else:
                user_prompt = "Hello"

            state = {
                "messages": [HumanMessage(content=user_prompt)],
                "channel_id": cid,
            }
            
            config = {
                "configurable": {
                    "thread_id": str(cid),
                    "deps": deps,
                }
            }

            try:
                # Run the graph
                final_state = await graph.ainvoke(state, config=config)
                
                # Get the final AI message
                last_msg = final_state["messages"][-1]
                if isinstance(last_msg, AIMessage):
                    await easy_send(channel, last_msg.content)
                else:
                    await channel.send("System: Agent failed to return a valid response.")
            except Exception as e:
                logfire.error("agent_run_error", error=e)
                await channel.send(f"System: Agent error — {type(e).__name__}")

async def setup(bot: commands.Bot) -> None:
    # Cleanup old checkpoints on startup
    memory_store.cleanup_old_checkpoints()
    await bot.add_cog(AgentCog(bot=bot))
