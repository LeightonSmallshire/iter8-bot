import asyncio
import os
import re
import textwrap
import traceback
from datetime import datetime
from typing import Any

import discord
import logfire
from discord.ext import commands
from dotenv import load_dotenv
from mem0 import MemoryClient
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from .agent_elmo import tools
from .agent_elmo.deps import BaseDeps, MainDeps
from .agent_elmo.modal_manager import ModalManager
from .agent_elmo.persistence import Persistence

# --- Configuration ---
TRUSTED_USERS: set[int] = {1416017385596653649, 1326156803108503566}

# --- Initialization ---
load_dotenv("data/.env")
load_dotenv()

logfire.configure(console=logfire.ConsoleOptions(min_log_level="debug"))
logfire.instrument_pydantic_ai()
# logfire.instrument_system_metrics()

# Initialize components
db = Persistence()
docker_manager = ModalManager()  # Using Modal instead of Docker (crashes if Modal not available)
mem0_client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

toolsets = [
    tools.spawn_toolset,
    tools.memory_toolset,
    # tools.docker_toolset,
    tools.discord_toolset,
]


# --- Main Agent ---
AGENT_MAIN: Agent[MainDeps] = Agent("openrouter:openrouter/free", deps_type=MainDeps, toolsets=toolsets)

# Register individual tools (web_search, batch_yes_no)
AGENT_MAIN.tool(tools.web_search)
AGENT_MAIN.tool(tools.batch_yes_no)
AGENT_MAIN.tool(tools.run_python_code)


@AGENT_MAIN.system_prompt
async def dynamic_system_prompt(ctx: RunContext[MainDeps]) -> str:
    bot_name = ctx.deps.bot.user.display_name if ctx.deps.bot.user else "Assistant"
    return textwrap.dedent(f"""
        You are an advanced Discord AI assistant with multiple capabilities:

        TIME: {datetime.now().strftime("%H:%M")}
        MY NAME: {bot_name}

        You have access to tools for web search, Docker container operations, task spawning, and memory management via mem0.
        Tool docstrings describe their functionality - use them proactively when they help answer the user's question.

        TASK TOOL:
        Use the 'task' tool to spawn a sub-agent with a custom system prompt and initial message.
        Example usage:
        - system_prompt: "You are a coding expert. Use Docker tools to write and test code."
        - initial_message: "Write a Python script to calculate fibonacci numbers"

        MEMORY:
        You have access to mem0 for semantic memory. Use these tools:
        - remember: Explicitly save information to memory
        - recall: Search memories using semantic search
        """).strip()


def split_message_for_discord(message: str) -> list[str]:
    pattern = re.compile(r"(```[\s\S]*?```|`[^`\n]+`|\|\|[\s\S]+?\|\|)")

    partial = ""
    complete_chunks = []

    for part in pattern.split(message):
        if not part:
            continue

        if len(partial) + len(part) <= 1900:
            partial = partial + part
            continue

        if len(partial) > 0:
            complete_chunks.append(partial)

        opener, closer = "", ""
        if part.startswith("```"):
            opener, closer = "```", "```"
        elif part.startswith("`"):
            opener, closer = "`", "`"
        elif part.startswith("||"):
            opener, closer = "||", "||"

        remainder = part
        while len(remainder) > 1900:
            chunk = remainder[:1900]
            if len(chunk) > 0:
                complete_chunks.append(opener + chunk + closer)
            remainder = remainder[1900:]
        partial = remainder

    if len(partial) > 0:
        complete_chunks.append(partial)

    return complete_chunks


async def easy_send(channel: discord.abc.Messageable, message: str) -> None:
    for chunk in split_message_for_discord(message):
        await channel.send(chunk)


class AgentCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Persistence, docker_manager: BaseDeps, mem0_client: MemoryClient) -> None:
        self.bot = bot
        self.db = db
        self.docker_manager = docker_manager
        self.mem0_client = mem0_client
        self.allowed_channels: set[int] = {1498977340821209198, 1432698704191815680, 1439936991096737804}
        self.silence_tasks: dict[int, asyncio.Task[Any]] = {}
        self.run_tasks: dict[int, asyncio.Task[Any]] = {}
        self.pending_messages: dict[int, discord.Message] = {}
        self.message_queues: dict[int, list[discord.Message]] = {}
        self.is_processing: set[int] = set()
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

        if not (is_mentioned or is_reply):
            return

        cid = channel_id

        # If processing, queue for immediate processing after current response
        if cid in self.is_processing:
            self.message_queues.setdefault(cid, []).append(message)
            return

        # Otherwise, (re)start the silence timer
        self.pending_messages[cid] = message
        if cid in self.silence_tasks:
            self.silence_tasks[cid].cancel()

        async def wait_for_silence() -> None:
            try:
                await asyncio.sleep(self.SILENCE_DELAY)
                if cid in self.pending_messages:
                    msg = self.pending_messages.pop(cid)
                    await self._process_queue(cid, msg)
            except asyncio.CancelledError:
                pass
            finally:
                if cid in self.silence_tasks and self.silence_tasks[cid].done():
                    del self.silence_tasks[cid]

        self.silence_tasks[cid] = asyncio.create_task(wait_for_silence())

    async def _process_queue(self, cid: int, initial_msg: discord.Message) -> None:
        self.is_processing.add(cid)
        msg = initial_msg
        try:
            while msg:
                task = asyncio.create_task(self.run_agent(msg.channel, user_message=msg))
                self.run_tasks[cid] = task
                await task
                queue = self.message_queues.get(cid, [])
                msg = queue.pop(0) if queue else None
        finally:
            self.is_processing.discard(cid)
            if cid in self.run_tasks and self.run_tasks[cid].done():
                del self.run_tasks[cid]

    @logfire.instrument
    async def run_agent(self, channel: discord.abc.Messageable, user_message: discord.Message | None = None) -> None:
        history: list[ModelMessage] = []
        before = discord.Object(id=user_message.id) if user_message else None
        async for msg in channel.history(limit=20, before=before):
            if self.bot.user and msg.author.id == self.bot.user.id:
                history.append(ModelResponse(parts=[TextPart(content=msg.clean_content)]))
            else:
                author_name = msg.author.name if msg.author else "Unknown"
                history.append(ModelRequest(parts=[UserPromptPart(content=f"{author_name}: {msg.clean_content}")]))
        history.reverse()

        author_name = user_message.author.name if user_message and user_message.author else "Unknown"
        user_prompt = f"{author_name}: {user_message.clean_content}" if user_message else ""
        message_history = history if history else []

        async with channel.typing():
            deps = MainDeps(
                channel_id=getattr(channel, "id", 0),
                db=self.db,
                docker_manager=self.docker_manager,
                bot=self.bot,
                mem0_client=self.mem0_client,
            )

            for attempt in range(3):
                try:
                    result = await AGENT_MAIN.run(user_prompt, deps=deps, message_history=message_history)
                    break
                except Exception as e:
                    logfire.error("model_attempt_failed", attempt=attempt, error=e)
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt * 2)
                    else:
                        traceback.print_exception(e)
                        await easy_send(channel, f"Model failed after 3 attempts:\n{e}")
                        raise

            if result.output:
                await easy_send(channel, result.output)
            else:
                await easy_send(channel, "(no output)")

            messages_to_save = [
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": result.output if result.output else "(no output)"},
            ]
            mem0_client.add(messages_to_save, user_id=str(getattr(channel, "id", 0)))


if __name__ == "__main__":
    # Create bot with command prefix (even if not using commands, needed for Cog)
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        # Load the AgentCog
        await bot.add_cog(
            AgentCog(
                bot=bot,
                db=db,
                docker_manager=docker_manager,
                mem0_client=mem0_client,
            )
        )
        logfire.info("bot_ready", bot_id=bot.user.id if bot.user else None)

    try:
        bot.run(os.environ["DISCORD_BOT_TOKEN"])
    except KeyboardInterrupt:
        pass
    finally:
        logfire.info("bot_shutdown")

# --- Cog Setup Function (MANDATORY for extensions) ---


async def setup(bot: commands.Bot):
    await bot.add_cog(
        AgentCog(
            bot=bot,
            db=db,
            docker_manager=docker_manager,
            mem0_client=mem0_client,
        )
    )


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{AgentCog.qualified_name}' unloaded.")
