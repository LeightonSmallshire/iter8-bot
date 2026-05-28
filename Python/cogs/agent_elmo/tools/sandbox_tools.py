import pydantic_monty
from langchain_core.tools import tool
from ..sandbox.manager import Sandbox

@tool
async def bash(command: str, sandbox: Sandbox, channel_id: int, timeout: int = 30) -> str:
    """Execute a bash command in the sandboxed environment."""
    result = await sandbox.exec_command(command, channel_id, timeout)
    return f"Exit code: {result.exit_code}\nOutput:\n{result.output}"

@tool
async def read_file(path: str, sandbox: Sandbox, channel_id: int) -> str:
    """Read a file from the sandboxed filesystem."""
    return await sandbox.read_file(path, channel_id)

@tool
async def write_file(path: str, content: str, sandbox: Sandbox, channel_id: int) -> str:
    """Write/overwrite a file in the sandboxed filesystem."""
    return await sandbox.write_file(path, content, channel_id)

@tool
async def edit_file(path: str, old_text: str, new_text: str, sandbox: Sandbox, channel_id: int, occurrence: int = 1) -> str:
    """Edit a file by replacing old_text with new_text."""
    return await sandbox.edit_file(path, old_text, new_text, channel_id, occurrence)

@tool
async def list_dir(sandbox: Sandbox, channel_id: int, path: str = "/workspace", recursive: bool = False) -> str:
    """List files and directories in a path."""
    return await sandbox.list_dir(path, channel_id, recursive)

@tool
async def glob_files(sandbox: Sandbox, channel_id: int, pattern: str, path: str = "/workspace") -> str:
    """Find files matching a glob pattern."""
    return await sandbox.glob_files(pattern, channel_id, path)

@tool
async def grep_files(sandbox: Sandbox, channel_id: int, pattern: str, path: str = "/workspace", file_glob: str = "**/*", case_sensitive: bool = False, max_results: int = 50) -> str:
    """Search for regex pattern in files."""
    return await sandbox.grep_files(pattern, channel_id, path, file_glob, case_sensitive, max_results)

@tool
async def find_files(sandbox: Sandbox, channel_id: int, name_pattern: str, path: str = "/workspace") -> str:
    """Find files by name pattern."""
    return await sandbox.find_files(name_pattern, channel_id, path)

@tool
async def make_dir(path: str, sandbox: Sandbox, channel_id: int) -> str:
    """Create a directory."""
    return await sandbox.make_dir(path, channel_id)

@tool
async def delete_file(path: str, sandbox: Sandbox, channel_id: int) -> str:
    """Delete a file or directory."""
    return await sandbox.delete_file(path, channel_id)

@tool
async def run_python(code: str) -> str:
    """Executes Python code using pydantic-monty for type-safe sandboxing."""
    try:
        m = pydantic_monty.Monty(code)
        m.type_check()
        output = pydantic_monty.CollectStreams()
        result = m.run(external_functions={}, print_callback=output)
        return f"stdout:\n{output.output}\n\nFinal result: {result}"
    except pydantic_monty.MontyTypingError as e:
        return f"Type checking failed: {e.display('concise')}"
    except pydantic_monty.MontyError as e:
        return f"Execution Failed: {e}"
    except Exception as e:
        return f"Unexpected Error: {e}"
