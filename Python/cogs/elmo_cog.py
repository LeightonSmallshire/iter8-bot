import re
import os
import asyncio
import discord
from discord.ext import commands
import traceback
import logfire
import textwrap
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, List, Optional, Any, Set
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart

# Local imports
from .agent_elmo import tools
from .agent_elmo.persistence import Persistence
from .agent_elmo.docker_manager import DockerManager
from .agent_elmo.deps import MainDeps
from .agent_elmo import sub_agents

# --- Configuration ---
TRUSTED_USERS: Set[int] = {1416017385596653649, 1326156803108503566}

# --- Initialization ---
load_dotenv()
logfire.configure(console=logfire.ConsoleOptions(min_log_level='debug'))
logfire.instrument_pydantic_ai()

# Initialize components
db = Persistence()
docker_manager = DockerManager()

# --- Main Agent ---
AGENT_MAIN: Agent[MainDeps] = Agent(
    "openrouter:openrouter/free",
    deps_type=MainDeps,
    toolsets=[tools.docker_toolset, tools.spawn_toolset, tools.memory_toolset],
)

# Create sub-agents
AGENT_CODER = sub_agents.create_coder_agent()
AGENT_RESEARCHER = sub_agents.create_researcher_agent()
AGENT_ANALYST = sub_agents.create_analyst_agent()
AGENT_YES_NO = sub_agents.create_yes_no_agent()

# Register individual tools (web_search, batch_yes_no)
AGENT_MAIN.tool(tools.web_search)
AGENT_MAIN.tool(tools.batch_yes_no)


@AGENT_MAIN.system_prompt
async def dynamic_system_prompt(ctx: RunContext[MainDeps]) -> str:
    return textwrap.dedent(f"""
        You are an advanced Discord AI assistant with multiple capabilities:

        TIME: {datetime.now().strftime("%H:%M")}
        TODO LIST: {ctx.deps.db.get_todos()}
        PAST FACTS: {ctx.deps.db.get_facts()}

        You have access to tools for web search, Docker container operations, sub-agent spawning, and memory management.
        Tool docstrings describe their functionality - use them proactively when they help answer the user's question.

        SUB-AGENTS:
        You can spawn specialized sub-agents for complex tasks. Sub-agents can recursively spawn other sub-agents if needed.
        - Use spawn_coder for: writing code, debugging, code review, scripting
        - Use spawn_researcher for: web research, fact-finding, information gathering
        - Use spawn_analyst for: data analysis, pattern recognition, data processing

        DOCKER:
        You have access to a Python 3.12 Docker container. Use these tools to work with files:
        - docker_ls: List files and directories (like ls command)
        - docker_read: Read file contents
        - docker_write: Create/overwrite a file
        - docker_edit: Edit file by replacing text chunks (better than rewrite)
        - docker_grep: Search for patterns in files (like grep command)
        - docker_glob: Find files by glob pattern (like glob **/*.py)
        - docker_find: Find files by name pattern
        - docker_mkdir: Create directories
        - docker_rm: Delete files or directories
        - docker_exec: Run commands in the container""").strip()


def split_message_for_discord(message: str) -> list[str]:
    pattern = re.compile(r'(```[\s\S]*?```|`[^`\n]+`|\|\|[\s\S]+?\|\|)')

    partial = ''
    complete_chunks = []

    for part in pattern.split(message):
        if not part:
            continue

        if len(partial) + len(part) <= 1900:
            partial = partial + part
            continue

        complete_chunks.append(partial)

        opener, closer = '', ''
        if part.startswith('```'):
            opener, closer = '```', '```'
        elif part.startswith('`'):
            opener, closer = '`', '`'
        elif part.startswith('||'):
            opener, closer = '||', '||'

        remainder = part
        while len(remainder) > 1900:
            chunk = remainder[:1900]
            complete_chunks.append(opener + chunk + closer)
            remainder = remainder[1900:]
        partial = remainder

    if partial:
        complete_chunks.append(partial)

    return complete_chunks


async def easy_send(channel: discord.abc.Messageable, message: str) -> None:
    for chunk in split_message_for_discord(message):
        await channel.send(chunk)


class AgentCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        db: Persistence,
        docker_manager: DockerManager,
        agent_main: Agent[MainDeps],
        coder_agent: Agent[Any],
        researcher_agent: Agent[Any],
        analyst_agent: Agent[Any],
        yes_no_agent: Agent[Any],
    ) -> None:
        self.bot = bot
        self.db = db
        self.docker_manager = docker_manager
        self.agent_main = agent_main
        self.coder_agent = coder_agent
        self.researcher_agent = researcher_agent
        self.analyst_agent = analyst_agent
        self.yes_no_agent = yes_no_agent
        # self.allowed_channels: Set[int] = {1498977340821209198, 1432698704191815680}
        self.debounce_tasks: Dict[int, asyncio.Task[Any]] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        # Type-safe channel ID check
        channel_id: Optional[int] = getattr(message.channel, 'id', None)
        if channel_id is None:  # or channel_id not in self.allowed_channels:
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
            if cid in self.debounce_tasks:
                self.debounce_tasks[cid].cancel()
            self.debounce_tasks[cid] = asyncio.create_task(self.delayed_run(message))

    async def delayed_run(self, message: discord.Message) -> None:
        try:
            await asyncio.sleep(3.0)
            await self.run_agent(message.channel)
        except asyncio.CancelledError:
            pass

    async def run_agent(self, channel: discord.abc.Messageable) -> None:
        with logfire.span("run_agent", channel_id=getattr(channel, 'id', 0)):
            history: List[ModelMessage] = []
            async for msg in channel.history(limit=20):
                if self.bot.user and msg.author.id == self.bot.user.id:
                    history.append(ModelResponse(parts=[TextPart(content=msg.clean_content)]))
                else:
                    author_name = msg.author.name if msg.author else "Unknown"
                    history.append(ModelRequest(parts=[UserPromptPart(content=f"{author_name}: {msg.clean_content}")]))
            history.reverse()
            logfire.debug("history_loaded", message_count=len(history))

            async with channel.typing():
                deps = MainDeps(
                    channel_id=getattr(channel, 'id', 0),
                    db=self.db,
                    docker_manager=self.docker_manager,
                    coder_agent=self.coder_agent,
                    researcher_agent=self.researcher_agent,
                    analyst_agent=self.analyst_agent,
                    yes_no_agent=self.yes_no_agent,
                )

                # Get the last message content safely
                last_message = history[-1] if history else None
                user_prompt: str = ""
                if last_message and isinstance(last_message, ModelRequest):
                    parts = last_message.parts
                    if parts and isinstance(parts[0], UserPromptPart):
                        user_prompt = str(parts[0].content)

                message_history = history[:-1] if len(history) > 1 else []

                try:
                    result = await self.agent_main.run(user_prompt, deps=deps, message_history=message_history)
                    if result.output:
                        await easy_send(channel, result.output)
                    else:
                        await easy_send(channel, '(no output)')

                except Exception as e:
                    traceback.print_exception(e)
                    logfire.error("agent_error", error=str(e))
                    await easy_send(channel, ''.join(traceback.format_exception(e)))

                logfire.debug("agent_complete")

    async def cog_unload(self) -> None:
        """Clean up resources when cog is unloaded."""
        self.docker_manager.stop()
        # Cancel any pending debounce tasks
        for task in self.debounce_tasks.values():
            task.cancel()


if __name__ == "__main__":
    # Create bot with command prefix (even if not using commands, needed for Cog)
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready() -> None:
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        # Load the AgentCog
        await bot.add_cog(AgentCog(
            bot=bot,
            db=db,
            docker_manager=docker_manager,
            agent_main=AGENT_MAIN,
            coder_agent=AGENT_CODER,
            researcher_agent=AGENT_RESEARCHER,
            analyst_agent=AGENT_ANALYST,
            yes_no_agent=AGENT_YES_NO,
        ))
        logfire.info("bot_ready", bot_id=bot.user.id if bot.user else None)

    try:
        bot.run(os.environ["DISCORD_BOT_TOKEN"])
    except KeyboardInterrupt:
        pass
    finally:
        logfire.info("bot_shutdown")


# --- Cog Setup Function (MANDATORY for extensions) ---

async def setup(bot: commands.Bot):
    await bot.add_cog(AgentCog(
        bot=bot,
        db=db,
        docker_manager=docker_manager,
        agent_main=AGENT_MAIN,
        coder_agent=AGENT_CODER,
        researcher_agent=AGENT_RESEARCHER,
        analyst_agent=AGENT_ANALYST,
        yes_no_agent=AGENT_YES_NO,
    ))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{AgentCog.qualified_name}' unloaded.")
