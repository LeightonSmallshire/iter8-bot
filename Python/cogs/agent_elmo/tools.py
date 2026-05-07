import asyncio
import os
from typing import List, Optional
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset
import pydantic_monty
import logfire
from ddgs import DDGS
import aiohttp
from .deps import BaseDeps, MainDeps

# Lazy import for sub_agents to avoid circular imports
_sub_agents = None

def _get_sub_agents():
    global _sub_agents
    if _sub_agents is None:
        from . import sub_agents
        _sub_agents = sub_agents
    return _sub_agents

# Create sub-agents lazily
def _get_agent_coder():
    return _get_sub_agents().create_coder_agent()

def _get_agent_researcher():
    return _get_sub_agents().create_researcher_agent()

def _get_agent_analyst():
    return _get_sub_agents().create_analyst_agent()

def _get_agent_yes_no():
    return _get_sub_agents().create_yes_no_agent()

# Sub-agent instances (created on first use)
AGENT_CODER = None
AGENT_RESEARCHER = None
AGENT_ANALYST = None
AGENT_YES_NO = None

def _ensure_agents():
    global AGENT_CODER, AGENT_RESEARCHER, AGENT_ANALYST, AGENT_YES_NO
    if AGENT_CODER is None:
        AGENT_CODER = _get_agent_coder()
        AGENT_RESEARCHER = _get_agent_researcher()
        AGENT_ANALYST = _get_agent_analyst()
        AGENT_YES_NO = _get_agent_yes_no()


# --- Web Search Tool ---
@logfire.instrument(None, record_return=True)
async def web_search(ctx: RunContext[BaseDeps], query: str) -> str:
    """Search the web using DuckDuckGo."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=3):
            results.append(f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}")
    output = "\n\n".join(results) if results else "No results found."
    logfire.debug("web_search_result", result_count=len(results))
    return output


# --- Docker Tools ---
@logfire.instrument(None, record_return=True)
async def docker_exec(ctx: RunContext[BaseDeps], command: str, timeout: int = 30) -> str:
    """Execute a command in the Docker container.

    Args:
        command: Command to execute
        timeout: Maximum seconds to wait for command completion (default: 30)
    """
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        # Run blocking Docker operation in thread pool with timeout
        result = await asyncio.wait_for(
            asyncio.to_thread(docker_manager.exec_command, command, ctx.deps.channel_id, timeout),
            timeout=timeout
        )
        output: str = result.output
        if len(output) > 2000:
            output = output[:2000] + "\n... (output truncated)"
        logfire.debug("docker_exec_result", exit_code=result.exit_code, output_length=len(output))
        return f"Exit code: {result.exit_code}\nOutput:\n{output}"
    except Exception as e:
        logfire.error("docker_exec_error", error=str(e))
        return f"Error executing command: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_read(ctx: RunContext[BaseDeps], path: str) -> str:
    """Read a file from the Docker container."""
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        content: str = docker_manager.read_file(path, ctx.deps.channel_id)
        if len(content) > 2000:
            content = content[:2000] + "\n... (file truncated)"
        logfire.debug("docker_read_result", path=path, content_length=len(content))
        return content
    except Exception as e:
        logfire.error("docker_read_error", path=path, error=str(e))
        return f"Error reading file: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_write(ctx: RunContext[BaseDeps], path: str, content: str) -> str:
    """Write a file to the Docker container (creates or overwrites)."""
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        result = docker_manager.write_file(path, content, ctx.deps.channel_id)
        logfire.debug("docker_write_result", path=path)
        return str(result)
    except Exception as e:
        logfire.error("docker_write_error", path=path, error=str(e))
        return f"Error writing file: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_edit(ctx: RunContext[BaseDeps], path: str, old_text: str, new_text: str, occurrence: int = 1) -> str:
    """Edit a file by replacing old_text with new_text.

    Args:
        path: File path (e.g., /workspace/file.txt)
        old_text: Text to search for and replace
        new_text: Text to replace with
        occurrence: Which occurrence to replace (1-based, use -1 for all)
    """
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        result = docker_manager.edit_file(path, old_text, new_text, ctx.deps.channel_id, occurrence=occurrence)
        logfire.debug("docker_edit_result", path=path)
        return result
    except Exception as e:
        logfire.error("docker_edit_error", path=path, error=str(e))
        return f"Error editing file: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_ls(ctx: RunContext[BaseDeps], path: str = "/workspace", recursive: bool = False) -> str:
    """List files and directories in a path.

    Args:
        path: Directory path to list
        recursive: If True, list recursively
    """
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        result = docker_manager.list_dir(path, ctx.deps.channel_id, recursive=recursive)
        logfire.debug("docker_ls_result", path=path, output_length=len(result))
        return result
    except Exception as e:
        logfire.error("docker_ls_error", path=path, error=str(e))
        return f"Error listing directory: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_glob(ctx: RunContext[BaseDeps], pattern: str, path: str = "/workspace") -> str:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py")
        path: Base path to search from
    """
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        result = docker_manager.glob_files(pattern, ctx.deps.channel_id, path=path)
        logfire.debug("docker_glob_result", pattern=pattern, output_length=len(result))
        return result
    except Exception as e:
        logfire.error("docker_glob_error", pattern=pattern, error=str(e))
        return f"Error in glob search: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_grep(ctx: RunContext[BaseDeps], pattern: str, path: str = "/workspace",
                      file_glob: str = "**/*", case_sensitive: bool = False, max_results: int = 50) -> str:
    """Search for regex pattern in files.

    Args:
        pattern: Regex pattern to search for
        path: Base path to search
        file_glob: Glob pattern for files to search (e.g., "**/*.py")
        case_sensitive: Whether search is case sensitive
        max_results: Maximum number of results to return
    """
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        result = docker_manager.grep(pattern, ctx.deps.channel_id, path=path, file_glob=file_glob,
                                     case_sensitive=case_sensitive, max_results=max_results)
        logfire.debug("docker_grep_result", pattern=pattern, output_length=len(result))
        return result
    except Exception as e:
        logfire.error("docker_grep_error", pattern=pattern, error=str(e))
        return f"Error in grep search: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_find(ctx: RunContext[BaseDeps], name_pattern: str, path: str = "/workspace") -> str:
    """Find files by name pattern.

    Args:
        name_pattern: Pattern to match filename (e.g., "*.py" or "test_*.py")
        path: Base path to search
    """
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        result = docker_manager.find_files(name_pattern, ctx.deps.channel_id, path=path)
        logfire.debug("docker_find_result", name_pattern=name_pattern, output_length=len(result))
        return result
    except Exception as e:
        logfire.error("docker_find_error", name_pattern=name_pattern, error=str(e))
        return f"Error in find: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_mkdir(ctx: RunContext[BaseDeps], path: str) -> str:
    """Create a directory.

    Args:
        path: Directory path to create
    """
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        result = docker_manager.make_dir(path, ctx.deps.channel_id)
        logfire.debug("docker_mkdir_result", path=path)
        return result
    except Exception as e:
        logfire.error("docker_mkdir_error", path=path, error=str(e))
        return f"Error creating directory: {str(e)}"


@logfire.instrument(None, record_return=True)
async def docker_rm(ctx: RunContext[BaseDeps], path: str) -> str:
    """Delete a file or directory.

    Args:
        path: Path to delete
    """
    docker_manager = ctx.deps.docker_manager
    if not docker_manager.client:
        return "Docker is not available. Please ensure Docker is running."
    try:
        result = docker_manager.delete_file(path, ctx.deps.channel_id)
        logfire.debug("docker_rm_result", path=path)
        return result
    except Exception as e:
        logfire.error("docker_rm_error", path=path, error=str(e))
        return f"Error deleting: {str(e)}"


# --- Spawn Sub-Agent Tools, only usable by the main agent ---
@logfire.instrument(None, record_return=True)
async def spawn_coder(ctx: RunContext[MainDeps], task: str, use_docker: bool = True) -> str:
    """Spawn a specialized coding agent to handle coding tasks."""
    _ensure_agents()
    docker_manager = ctx.deps.docker_manager
    from deps import CoderDeps
    coder_deps = CoderDeps(docker_manager=docker_manager, channel_id=ctx.deps.channel_id)
    try:
        logfire.info("spawning_coder_agent", task=task)
        result = await AGENT_CODER.run(
            f"Task: {task}\n\n{'Use Docker tools to test and run code.' if use_docker else 'Do not use Docker.'}",
            deps=coder_deps
        )
        logfire.debug("coder_agent_result", output_length=len(result.output))
        return f"[Coder Agent Result]\n{result.output}"
    except Exception as e:
        logfire.error("spawn_coder_error", error=str(e))
        return f"Error spawning coder agent: {str(e)}"


@logfire.instrument(None, record_return=True)
async def spawn_researcher(ctx: RunContext[MainDeps], query: str, max_results: int = 5) -> str:
    """Spawn a specialized research agent to gather information."""
    _ensure_agents()
    docker_manager = ctx.deps.docker_manager
    from deps import ResearcherDeps
    researcher_deps = ResearcherDeps(docker_manager=docker_manager, channel_id=ctx.deps.channel_id)
    try:
        logfire.info("spawning_researcher_agent", query=query)
        result = await AGENT_RESEARCHER.run(
            f"Research Query: {query}\n\nPlease search the web and provide a comprehensive answer with sources. Max search results: {max_results}",
            deps=researcher_deps
        )
        logfire.debug("researcher_agent_result", output_length=len(result.output))
        return f"[Researcher Agent Result]\n{result.output}"
    except Exception as e:
        logfire.error("spawn_researcher_error", error=str(e))
        return f"Error spawning researcher agent: {str(e)}"


@logfire.instrument(None, record_return=True)
async def spawn_analyst(ctx: RunContext[MainDeps], data_description: str, analysis_task: str) -> str:
    """Spawn a specialized data analyst agent to analyze data."""
    _ensure_agents()
    docker_manager = ctx.deps.docker_manager
    from deps import AnalystDeps
    analyst_deps = AnalystDeps(docker_manager=docker_manager, channel_id=ctx.deps.channel_id)
    try:
        logfire.info("spawning_analyst_agent", task=analysis_task)
        result = await AGENT_ANALYST.run(
            f"Data: {data_description}\n\nTask: {analysis_task}\n\nUse Docker to process data if needed.",
            deps=analyst_deps
        )
        logfire.debug("analyst_agent_result", output_length=len(result.output))
        return f"[Analyst Agent Result]\n{result.output}"
    except Exception as e:
        logfire.error("spawn_analyst_error", error=str(e))
        return f"Error spawning analyst agent: {str(e)}"


# --- Batch Yes/No Tool ---
@logfire.instrument(None, record_return=True)
async def batch_yes_no(ctx: RunContext[MainDeps], question: str, items: List[str]) -> str:
    """Answer yes/no question for each item using a tiny agent."""
    _ensure_agents()
    docker_manager = ctx.deps.docker_manager
    from deps import YesNoDeps
    yes_no_deps = YesNoDeps(docker_manager=docker_manager, channel_id=ctx.deps.channel_id)
    results = []
    for item in items:
        try:
            formatted_question = question.replace("{item}", item)
            result = await AGENT_YES_NO.run(formatted_question, deps=yes_no_deps)
            answer = "yes" if result.output.answer else "no"
            results.append(f"{item}: {answer}")
            logfire.debug("yes_no_result", item=item, answer=answer)
        except Exception as e:
            logfire.error("yes_no_error", item=item, error=str(e))
            results.append(f"{item}: error")
    return "\n".join(results)


# --- Memory Tools ---
@logfire.instrument(None, record_return=True)
async def manage_todo(ctx: RunContext[MainDeps], task: str) -> str:
    """Add a new task to the todo list."""
    ctx.deps.db.add_todo(task)
    logfire.info("todo_added", task=task)
    return f"Added to todos: {task}"


@logfire.instrument(None, record_return=True)
async def record_fact(ctx: RunContext[MainDeps], fact: str) -> str:
    """Save information into long-term memory."""
    ctx.deps.db.add_fact(fact)
    logfire.info("fact_recorded", fact_length=len(fact))
    return f"Fact saved: {fact}"


@logfire.instrument(None, record_return=True)
async def run_python_code(ctx: RunContext[BaseDeps], code: str) -> str:
    """Executes Python code by pydantic-monty with the standard library"""

    try:
        m = pydantic_monty.Monty(code)
        m.type_check()

        output = pydantic_monty.CollectStreams()
        result = m.run(external_functions={
            # whatever external functions we want to give the agent's code
        }, print_callback=output)

        return f'stdout:\n{output.output}\n\nFinal result:{result}'

    except pydantic_monty.MontyTypingError as e:
        return f'The code failed type checking, fix the errors and retry:\n{e.display('concise')}'

    except pydantic_monty.MontyError as e:
        return f"Execution Failed: {e}"

    except Exception as e:
        return f"Unexpected Error: {e}"


# --- Discord Tools ---
TENOR_KEY = os.environ.get("TENOR_TOKEN", "")

@logfire.instrument(None, record_return=True)
async def read_history(ctx: RunContext[MainDeps], limit: int = 20) -> str:
    """Read message history from the current Discord channel.
    
    Args:
        limit: Number of messages to retrieve (default: 20, max: 50)
    """
    bot = ctx.deps.bot
    channel_id = ctx.deps.channel_id
    
    # Cap the limit
    limit = min(limit, 50)
    
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            return f"Error: Could not find channel with ID {channel_id}"
        
        messages = []
        async for msg in channel.history(limit=limit):
            author = msg.author.name if msg.author else "Unknown"
            content = msg.clean_content or "(no text)"
            messages.append(f"[{msg.created_at.strftime('%H:%M')}] {author}: {content}")
        
        messages.reverse()  # Oldest first
        return "\n".join(messages) if messages else "No messages found."
    except Exception as e:
        logfire.error("read_history_error", error=str(e))
        return f"Error reading history: {str(e)}"


@logfire.instrument(None, record_return=True)
async def send_gif(ctx: RunContext[MainDeps], query: str) -> str:
    """Send a GIF to the channel using Tenor.
    
    Args:
        query: Search query for the GIF (e.g., "happy", "dance", "thumbs up")
    """
    import discord
    
    if not TENOR_KEY:
        return "Error: Tenor API key not configured. Please set TENOR_TOKEN environment variable."
    
    bot = ctx.deps.bot
    channel_id = ctx.deps.channel_id
    
    try:
        url = "https://tenor.googleapis.com/v2/search"
        params = {
            "q": query,
            "key": TENOR_KEY,
            "media_filter": "gif,mediumgif",
            "limit": 10,
        }
        
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params) as r:
                data = await r.json()
        
        results = data.get("results", [])
        if not results:
            return f"No GIF found for query: {query}"
        
        import random
        # Pick a random result
        item = random.choice(results)
        mf = item.get("media_formats", {})
        gif_url = None
        for key in ("gif", "mediumgif", "tinygif"):
            if key in mf and "url" in mf[key]:
                gif_url = mf[key]["url"]
                break
        
        if not gif_url:
            return f"Error: Could not extract GIF URL for query: {query}"
        
        # Send the GIF
        channel = bot.get_channel(channel_id)
        if not channel:
            return f"Error: Could not find channel with ID {channel_id}"
        
        embed = discord.Embed()
        embed.set_image(url=gif_url)
        embed.set_footer(text="GIFs powered by Tenor", icon_url="https://tenor.com/assets/img/tenor-app-icon.png")
        await channel.send(embed=embed)
        return f"Sent GIF for: {query}"
        
    except Exception as e:
        logfire.error("send_gif_error", error=str(e))
        return f"Error sending GIF: {str(e)}"


@logfire.instrument(None, record_return=True)
async def timeout_user(ctx: RunContext[MainDeps], user_id: int, duration_seconds: int = 60) -> str:
    """Timeout (mute) a user in the guild for a specified duration.
    
    Args:
        user_id: The Discord user ID to timeout
        duration_seconds: Duration in seconds (max 300 seconds = 5 minutes)
    """
    import discord
    bot = ctx.deps.bot
    channel_id = ctx.deps.channel_id
    
    # Cap duration at 5 minutes (300 seconds) as per Discord limits for bots
    duration_seconds = min(duration_seconds, 300)
    
    try:
        # Get the guild from the channel
        channel = bot.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return "Error: Could not find text channel or invalid channel type."
        
        guild = channel.guild
        member = guild.get_member(user_id)
        
        if not member:
            return f"Error: Could not find user with ID {user_id} in this guild."
        
        # Calculate timeout duration
        from datetime import timedelta, datetime, timezone
        until = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)
        
        # Apply timeout
        await member.timeout(until, reason=f"Timeout requested by bot agent (user_id: {user_id})")
        return f"User {member.name} (ID: {user_id}) timed out for {duration_seconds} seconds."
        
    except discord.Forbidden:
        return "Error: Bot doesn't have permission to timeout users. Need 'Moderate Members' permission."
    except discord.HTTPException as e:
        return f"Error: Failed to timeout user - {str(e)}"
    except Exception as e:
        logfire.error("timeout_user_error", error=str(e))
        return f"Error timing out user: {str(e)}"


# --- Toolsets ---
docker_toolset: FunctionToolset[MainDeps] = FunctionToolset(
    [
        docker_exec,
        docker_read,
        docker_write,
        docker_edit,
        docker_ls,
        docker_glob,
        docker_grep,
        docker_find,
        docker_mkdir,
        docker_rm,
    ]
)

spawn_toolset: FunctionToolset[MainDeps] = FunctionToolset(
    [
        spawn_coder,
        spawn_researcher,
        spawn_analyst,
    ]
)

memory_toolset: FunctionToolset[MainDeps] = FunctionToolset(
    [
        manage_todo,
        record_fact,
    ]
)

discord_toolset: FunctionToolset[MainDeps] = FunctionToolset(
    [
        read_history,
        send_gif,
        timeout_user,
    ]
)

# Web search and batch_yes_no are kept as individual tools since they're used differently
# web_search - available to all agents
# batch_yes_no - used by main agent for batch decisions
