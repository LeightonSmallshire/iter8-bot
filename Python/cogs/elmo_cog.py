import asyncio
import contextlib
import io
import os
import re
import textwrap
import traceback
from typing import Any

import discord
import logfire
from discord.ext import commands
from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from .agent_elmo import tools
from .agent_elmo.deps import MainDeps
from .agent_elmo.modal_manager import ModalManager
from .agent_elmo.persistence import Persistence

# --- Configuration ---
TRUSTED_USERS: set[int] = {1416017385596653649, 1326156803108503566}

# --- Initialization ---
load_dotenv("data/.env")
load_dotenv()

logfire.configure(console=logfire.ConsoleOptions(min_log_level="debug"))
logfire.instrument_pydantic_ai()

# Initialize components
db = Persistence()
docker_manager = ModalManager()  # Using Modal instead of Docker (crashes if Modal not available)

toolsets = [
    tools.spawn_toolset,
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
        You are evil elmo clone with tools.
        You may swear, send memes, talk about things NSFW. No limits.
        BDSM references are funny.

        MY NAME: {bot_name}

        You have access to tools for web search, subtask spawning, and memory management.
        Tool docstrings describe their functionality - use them proactively.
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
    def __init__(self, bot: commands.Bot,
                 db: Persistence,
                 docker_manager: ModalManager,
                 ) -> None:
        self.bot = bot
        self.db = db
        self.docker_manager = docker_manager
        self.allowed_channels: set[int] = {1498977340821209198, 1432698704191815680, 1439936991096737804}
        # Wait-for-silence state per channel
        self.silence_tasks: dict[int, asyncio.Task[Any]] = {}
        self.run_tasks: dict[int, asyncio.Task[Any]] = {}
        self.pending_messages: dict[int, discord.Message] = {}
        self.SILENCE_DELAY: float = 3.0  # Wait 3 seconds for silence

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        # Type-safe channel ID check
        channel_id: int | None = getattr(message.channel, "id", None)
        if channel_id is None or channel_id not in self.allowed_channels:
            return

        # Check if bot is mentioned
        is_mentioned = self.bot.user is not None and self.bot.user.mentioned_in(message)

        # Check if this is a reply to the bot
        is_reply = False
        if message.reference and message.reference.resolved:
            resolved = message.reference.resolved
            if isinstance(resolved, discord.Message) and self.bot.user:
                is_reply = resolved.author.id == self.bot.user.id

        if is_mentioned or is_reply:
            cid = channel_id

            # Store the latest message
            self.pending_messages[cid] = message

            # Cancel any existing silence task (re-trigger)
            if cid in self.silence_tasks:
                self.silence_tasks[cid].cancel()

            # Start a new silence task
            async def wait_for_silence() -> None:
                try:
                    await asyncio.sleep(self.SILENCE_DELAY)
                    # Silence achieved - get the pending message
                    if cid in self.pending_messages:
                        msg = self.pending_messages.pop(cid)
                        # Wait for current run to finish if any
                        if cid in self.run_tasks:
                            with contextlib.suppress(BaseException):
                                await self.run_tasks[cid]
                        # Start new run
                        task = asyncio.create_task(self.run_agent(msg.channel))
                        self.run_tasks[cid] = task
                        try:
                            await task
                        finally:
                            if cid in self.run_tasks:
                                del self.run_tasks[cid]
                except asyncio.CancelledError:
                    pass  # Re-triggered by new message
                finally:
                    # Clean up silence task reference
                    if cid in self.silence_tasks and self.silence_tasks[cid].done():
                        del self.silence_tasks[cid]

            self.silence_tasks[cid] = asyncio.create_task(wait_for_silence())

    @logfire.instrument
    async def run_agent(self, channel: discord.abc.Messageable) -> None:
        history: list[ModelMessage] = []
        async for msg in channel.history(limit=20):
            if self.bot.user and msg.author.id == self.bot.user.id:
                history.append(ModelResponse(parts=[TextPart(content=msg.clean_content)]))
            else:
                author_name = f'{msg.author.name} id={msg.author.id}' if msg.author else "Unknown"
                history.append(ModelRequest(parts=[UserPromptPart(content=f"{author_name}: {msg.clean_content}")]))
        history.reverse()

        async with channel.typing():
            deps = MainDeps(
                channel_id=getattr(channel, "id", 0),
                db=self.db,
                docker_manager=self.docker_manager,
                bot=self.bot,
            )

            # Get the last message content safely
            last_message = history[-1] if history else None
            user_prompt: str = ""
            if last_message and isinstance(last_message, ModelRequest):
                parts = last_message.parts
                if parts and isinstance(parts[0], UserPromptPart):
                    user_prompt = str(parts[0].content)

            message_history = history[:-1] if len(history) > 1 else []

            for _ in range(3):  # try 3 times
                try:
                    result = await AGENT_MAIN.run(user_prompt, deps=deps, message_history=message_history)
                    result.output = result.output if result.output else '(no output)'

                    await easy_send(channel, result.output)

                    return
                except Exception as e:
                    logfire.error("agent_error", error=e)
                    f = io.BytesIO('\n'.join(traceback.format_exception(e)).encode('utf-8'))
                    await channel.send('System: Retrying...', file=discord.File(f, 'Exception.txt'))

            await channel.send('System: Failed to run LLM')


if __name__ == "__main__":
    # Create bot with command prefix (even if not using commands, needed for Cog)
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        if bot.user:
            print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        # Load the AgentCog
        await bot.add_cog(
            AgentCog(
                bot=bot,
                db=db,
                docker_manager=docker_manager,
            )
        )
        logfire.info("bot_ready", bot_id=bot.user.id if bot.user else None)

    try:
        bot.run(os.environ["DISCORD_BOT_TOKEN"])
    except KeyboardInterrupt:
        pass
    finally:
        logfire.info("bot_shutdown")


async def setup(bot: commands.Bot):
    await bot.add_cog(
        AgentCog(
            bot=bot,
            db=db,
            docker_manager=docker_manager,
        )
    )
