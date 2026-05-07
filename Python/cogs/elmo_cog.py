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
from mem0 import MemoryClient

# --- Configuration ---
TRUSTED_USERS: Set[int] = {1416017385596653649, 1326156803108503566}

# --- Initialization ---
load_dotenv('data/.env')
load_dotenv()

logfire.configure(console=logfire.ConsoleOptions(min_log_level='debug'))
logfire.instrument_pydantic_ai()
# logfire.instrument_system_metrics()

# Initialize components
db = Persistence()
docker_manager = DockerManager()
mem0_client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])

toolsets = [
    tools.spawn_toolset,
    tools.memory_toolset
]
if docker_manager.client is not None:
    toolsets.append(tools.docker_toolset)


# --- Main Agent ---
AGENT_MAIN: Agent[MainDeps] = Agent(
    "openrouter:openrouter/free",
    deps_type=MainDeps,
    toolsets=toolsets
)

# Register individual tools (web_search, batch_yes_no)
AGENT_MAIN.tool(tools.web_search)
AGENT_MAIN.tool(tools.batch_yes_no)
AGENT_MAIN.tool(tools.run_python_code)


@AGENT_MAIN.system_prompt
async def dynamic_system_prompt(ctx: RunContext[MainDeps]) -> str:
    return textwrap.dedent(f"""
        You are an advanced Discord AI assistant with multiple capabilities:
        
        TIME: {datetime.now().strftime("%H:%M")}
        
        You have access to tools for web search, Docker container operations, sub-agent spawning, and memory management via mem0.
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
        - docker_exec: Run commands in the container
        
        MEMORY:
        You have access to mem0 for semantic memory. Use these tools:
        - remember: Explicitly save information to memory
        - recall: Search memories using semantic search
        - manage_todo: Add tasks to the TODO list""").strip()


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

        if len(partial) > 0:
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
    def __init__(
        self,
        bot: commands.Bot,
        db: Persistence,
        docker_manager: DockerManager,
        mem0_client: MemoryClient
    ) -> None:
        self.bot = bot
        self.db = db
        self.docker_manager = docker_manager
        self.mem0_client = mem0_client
        self.allowed_channels: Set[int] = {1498977340821209198, 1432698704191815680, 1439936991096737804}
        # Wait-for-silence state per channel
        self.silence_tasks: Dict[int, asyncio.Task[Any]] = {}
        self.run_tasks: Dict[int, asyncio.Task[Any]] = {}
        self.pending_messages: Dict[int, discord.Message] = {}
        self.SILENCE_DELAY: float = 3.0  # Wait 3 seconds for silence

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        # Type-safe channel ID check
        channel_id: Optional[int] = getattr(message.channel, 'id', None)
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
                            try:
                                await self.run_tasks[cid]
                            except BaseException:
                                pass
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
        history: List[ModelMessage] = []
        async for msg in channel.history(limit=20):
            if self.bot.user and msg.author.id == self.bot.user.id:
                history.append(ModelResponse(parts=[TextPart(content=msg.clean_content)]))
            else:
                author_name = msg.author.name if msg.author else 'Unknown'
                history.append(ModelRequest(parts=[UserPromptPart(content=f'{author_name}: {msg.clean_content}')]))
        history.reverse()

        # Inject TODO list as a message in history (not system prompt)
        todos = self.db.get_todos()
        if todos and 'No active tasks' not in todos:
            todo_msg = ModelRequest(parts=[UserPromptPart(content=f"[System: Current TODO list:\n{todos}")])
            history.insert(0, todo_msg)

        async with channel.typing():
            deps = MainDeps(
                channel_id=getattr(channel, 'id', 0),
                db=self.db,
                docker_manager=self.docker_manager,
                bot=self.bot,
                mem0_client=self.mem0_client,
            )

            # Get the last message content safely
            last_message = history[-1] if history else None
            user_prompt: str = ''
            if last_message and isinstance(last_message, ModelRequest):
                parts = last_message.parts
                if parts and isinstance(parts[0], UserPromptPart):
                    user_prompt = str(parts[0].content)

            message_history = history[:-1] if len(history) > 1 else []

            try:
                result = await AGENT_MAIN.run(user_prompt, deps=deps, message_history=message_history)
                if result.output:
                    await easy_send(channel, result.output)
                else:
                    await easy_send(channel, '(no output)')

                    # Save just the user's message and agent's response
                    messages_to_save = [
                        {'role': 'user', 'content': user_prompt},
                        {'role': 'assistant', 'content': result.output if result.output else '(no output)'}
                    ]
                    # Pass user_id as kwarg (not in filters)
                    mem0_client.add(messages_to_save, user_id=str(getattr(channel, 'id', 0)))
            except Exception as e:
                traceback.print_exception(e)
                logfire.error('agent_error', error=e)
                await easy_send(channel, ''.join(traceback.format_exception(e)))


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
            mem0_client=mem0_client,
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
        mem0_client=mem0_client,
    ))

# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{AgentCog.qualified_name}' unloaded.")
