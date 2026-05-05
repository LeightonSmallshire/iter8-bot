import asyncio
from typing import List
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset
import logfire
from ddgs import DDGS
from .deps import BaseDeps, MainDeps


# --- Web Search Tool ---
async def web_search(ctx: RunContext[BaseDeps], query: str) -> str:
    """Search the web using DuckDuckGo."""
    with logfire.span("web_search", query=query):
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append(f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}")
        output = "\n\n".join(results) if results else "No results found."
        logfire.debug("web_search_result", result_count=len(results))
        return output


# --- Docker Tools ---
async def docker_exec(ctx: RunContext[BaseDeps], command: str, timeout: int = 30) -> str:
    """Execute a command in the Docker container.

    Args:
        command: Command to execute
        timeout: Maximum seconds to wait for command completion (default: 30)
    """
    with logfire.span("docker_exec", command=command):
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


async def docker_read(ctx: RunContext[BaseDeps], path: str) -> str:
    """Read a file from the Docker container."""
    with logfire.span("docker_read", path=path):
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


async def docker_write(ctx: RunContext[BaseDeps], path: str, content: str) -> str:
    """Write a file to the Docker container (creates or overwrites)."""
    with logfire.span("docker_write", path=path, content_length=len(content)):
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


async def docker_edit(ctx: RunContext[BaseDeps], path: str, old_text: str, new_text: str, occurrence: int = 1) -> str:
    """Edit a file by replacing old_text with new_text.

    Args:
        path: File path (e.g., /workspace/file.txt)
        old_text: Text to search for and replace
        new_text: Text to replace with
        occurrence: Which occurrence to replace (1-based, use -1 for all)
    """
    with logfire.span("docker_edit", path=path, occurrence=occurrence):
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


async def docker_ls(ctx: RunContext[BaseDeps], path: str = "/workspace", recursive: bool = False) -> str:
    """List files and directories in a path.

    Args:
        path: Directory path to list
        recursive: If True, list recursively
    """
    with logfire.span("docker_ls", path=path, recursive=recursive):
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


async def docker_glob(ctx: RunContext[BaseDeps], pattern: str, path: str = "/workspace") -> str:
    """Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.py")
        path: Base path to search from
    """
    with logfire.span("docker_glob", pattern=pattern, path=path):
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
    with logfire.span("docker_grep", pattern=pattern, path=path, file_glob=file_glob):
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


async def docker_find(ctx: RunContext[BaseDeps], name_pattern: str, path: str = "/workspace") -> str:
    """Find files by name pattern.

    Args:
        name_pattern: Pattern to match filename (e.g., "*.py" or "test_*.py")
        path: Base path to search
    """
    with logfire.span("docker_find", name_pattern=name_pattern, path=path):
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


async def docker_mkdir(ctx: RunContext[BaseDeps], path: str) -> str:
    """Create a directory.

    Args:
        path: Directory path to create
    """
    with logfire.span("docker_mkdir", path=path):
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


async def docker_rm(ctx: RunContext[BaseDeps], path: str) -> str:
    """Delete a file or directory.

    Args:
        path: Path to delete
    """
    with logfire.span("docker_rm", path=path):
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
async def spawn_coder(ctx: RunContext[MainDeps], task: str, use_docker: bool = True) -> str:
    """Spawn a specialized coding agent to handle coding tasks."""
    with logfire.span("spawn_coder", task=task, use_docker=use_docker):
        coder_agent = ctx.deps.coder_agent
        docker_manager = ctx.deps.docker_manager
        from deps import CoderDeps
        coder_deps = CoderDeps(docker_manager=docker_manager, channel_id=ctx.deps.channel_id)
        try:
            logfire.info("spawning_coder_agent", task=task)
            result = await coder_agent.run(
                f"Task: {task}\n\n{'Use Docker tools to test and run code.' if use_docker else 'Do not use Docker.'}",
                deps=coder_deps
            )
            logfire.debug("coder_agent_result", output_length=len(result.output))
            return f"[Coder Agent Result]\n{result.output}"
        except Exception as e:
            logfire.error("spawn_coder_error", error=str(e))
            return f"Error spawning coder agent: {str(e)}"


async def spawn_researcher(ctx: RunContext[MainDeps], query: str, max_results: int = 5) -> str:
    """Spawn a specialized research agent to gather information."""
    with logfire.span("spawn_researcher", query=query, max_results=max_results):
        researcher_agent = ctx.deps.researcher_agent
        docker_manager = ctx.deps.docker_manager
        from deps import ResearcherDeps
        researcher_deps = ResearcherDeps(docker_manager=docker_manager, channel_id=ctx.deps.channel_id)
        try:
            logfire.info("spawning_researcher_agent", query=query)
            result = await researcher_agent.run(
                f"Research Query: {query}\n\nPlease search the web and provide a comprehensive answer with sources. Max search results: {max_results}",
                deps=researcher_deps
            )
            logfire.debug("researcher_agent_result", output_length=len(result.output))
            return f"[Researcher Agent Result]\n{result.output}"
        except Exception as e:
            logfire.error("spawn_researcher_error", error=str(e))
            return f"Error spawning researcher agent: {str(e)}"


async def spawn_analyst(ctx: RunContext[MainDeps], data_description: str, analysis_task: str) -> str:
    """Spawn a specialized data analyst agent to analyze data."""
    with logfire.span("spawn_analyst", data_description=data_description, analysis_task=analysis_task):
        analyst_agent = ctx.deps.analyst_agent
        docker_manager = ctx.deps.docker_manager
        from deps import AnalystDeps
        analyst_deps = AnalystDeps(docker_manager=docker_manager, channel_id=ctx.deps.channel_id)
        try:
            logfire.info("spawning_analyst_agent", task=analysis_task)
            result = await analyst_agent.run(
                f"Data: {data_description}\n\nTask: {analysis_task}\n\nUse Docker to process data if needed.",
                deps=analyst_deps
            )
            logfire.debug("analyst_agent_result", output_length=len(result.output))
            return f"[Analyst Agent Result]\n{result.output}"
        except Exception as e:
            logfire.error("spawn_analyst_error", error=str(e))
            return f"Error spawning analyst agent: {str(e)}"


# --- Batch Yes/No Tool ---
async def batch_yes_no(ctx: RunContext[MainDeps], question: str, items: List[str]) -> str:
    """Answer yes/no question for each item using a tiny agent."""
    with logfire.span("batch_yes_no", question=question, item_count=len(items)):
        yes_no_agent = ctx.deps.yes_no_agent
        docker_manager = ctx.deps.docker_manager
        from deps import YesNoDeps
        yes_no_deps = YesNoDeps(docker_manager=docker_manager, channel_id=ctx.deps.channel_id)
        results = []
        for item in items:
            try:
                formatted_question = question.replace("{item}", item)
                result = await yes_no_agent.run(formatted_question, deps=yes_no_deps)
                answer = "yes" if result.output.answer else "no"
                results.append(f"{item}: {answer}")
                logfire.debug("yes_no_result", item=item, answer=answer)
            except Exception as e:
                logfire.error("yes_no_error", item=item, error=str(e))
                results.append(f"{item}: error")
        return "\n".join(results)


# --- Memory Tools ---
async def manage_todo(ctx: RunContext[MainDeps], task: str) -> str:
    """Add a new task to the todo list."""
    with logfire.span("manage_todo", task=task):
        ctx.deps.db.add_todo(task)
        logfire.info("todo_added", task=task)
        return f"Added to todos: {task}"


async def record_fact(ctx: RunContext[MainDeps], fact: str) -> str:
    """Save information into long-term memory."""
    with logfire.span("record_fact", fact=fact[:100]):
        ctx.deps.db.add_fact(fact)
        logfire.info("fact_recorded", fact_length=len(fact))
        return f"Fact saved: {fact}"

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

# Web search and batch_yes_no are kept as individual tools since they're used differently
# web_search - available to all agents
# batch_yes_no - used by main agent for batch decisions
