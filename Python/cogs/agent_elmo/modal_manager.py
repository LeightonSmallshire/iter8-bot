"""Modal-based sandbox manager - replaces DockerManager for secure code execution.

Uses Modal (https://modal.com) for serverless sandboxed code execution.
Free tier: $30/mo recurring credits.

Interface matches DockerManager for drop-in replacement.
"""

import fnmatch
import os
import re
from dataclasses import dataclass

import logfire

# Modal import - will crash if not installed (matching pattern from mem0)
import modal


@dataclass
class ExecResult:
    """Result of a Modal command execution."""

    exit_code: int
    output: str


@dataclass
class FileMatch:
    """Result of a file search."""

    path: str
    line_number: int | None = None
    content: str | None = None


class ModalManager:
    """Manages Modal sandboxes for code execution.

    Provides the same interface as DockerManager for drop-in replacement.
    Each channel gets its own Modal volume for persistent storage.
    """

    def __init__(self, base_volume_name: str = "iter8-bot-workspaces"):
        self.base_volume_name: str = base_volume_name
        self.sandboxes: dict[int, modal.Sandbox] = {}  # channel_id -> sandbox
        self.volumes: dict[int, modal.Volume] = {}  # channel_id -> volume

        # Security: Command denylist - dangerous commands that should never execute
        self.denied_commands: frozenset = frozenset(
            {
                "rm",
                "rmdir",
                "docker",
                "ssh",
                "scp",
                "rsync",
                "sudo",
                "su",
                "chmod",
                "chown",
                "chgrp",
                "mkfs",
                "fdisk",
                "parted",
                "dd",
                "iptables",
                "ip6tables",
                "ufw",
                "firewall",
                "systemctl",
                "service",
                "init",
                "shutdown",
                "reboot",
            }
        )

    @logfire.instrument
    def ensure_sandbox(self, channel_id: int) -> modal.Sandbox:
        """Ensure a Modal sandbox is running for the given channel."""
        if channel_id in self.sandboxes:
            sandbox = self.sandboxes[channel_id]
            # Check if sandbox is still running
            try:
                # Modal sandboxes don't have a simple status check like Docker
                # We'll assume it's still running if it exists
                return sandbox
            except Exception:
                del self.sandboxes[channel_id]

        # Create or get volume for this channel
        volume_name = f"{self.base_volume_name}-{channel_id}"
        try:
            volume = modal.Volume.lookup(volume_name, create_if_missing=True)
            self.volumes[channel_id] = volume
        except Exception as e:
            logfire.error("modal_volume_error", error=str(e))
            raise Exception(f"Failed to create/get volume: {e}") from None

        # Create a sandbox with resource limits
        # Note: Modal sandboxes run with Python, we'll exec commands via subprocess
        sandbox = modal.Sandbox.create(
            "python3",
            "-c",
            "import time; time.sleep(3600)",  # Keep alive for 1 hour
            volumes={"/workspace": volume},
            memory=512,  # MB
            cpu=0.5,  # vCPU
            timeout=3600,  # 1 hour max
        )
        self.sandboxes[channel_id] = sandbox
        return sandbox

    @logfire.instrument
    def exec_command(self, cmd: str, channel_id: int = 0, timeout: int = 30) -> ExecResult:
        """Execute a command in the Modal sandbox for the given channel.

        Args:
            cmd: Command to execute
            channel_id: Channel ID for sandbox workspace
            timeout: Maximum seconds to wait for command completion (default: 30)

        Returns:
            ExecResult with exit_code and output
        """
        # Security: Check for denied commands
        cmd_lower = cmd.lower().strip()
        cmd_parts = cmd_lower.split()
        if cmd_parts:
            base_cmd = cmd_parts[0].split("/")[-1]  # Handle /usr/bin/rm style
            if base_cmd in self.denied_commands:
                logfire.warn("modal_exec_denied", command=cmd[:100], reason="denied_command")
                return ExecResult(
                    exit_code=-1, output=f"Error: Command '{base_cmd}' is not allowed for security reasons."
                )

        sandbox = self.ensure_sandbox(channel_id)
        try:
            # Execute command in sandbox
            result = sandbox.exec(cmd, timeout=timeout)
            output = result.stdout if result.stdout else ""
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"

            return ExecResult(exit_code=result.exit_code or 0, output=output)
        except Exception as e:
            logfire.error("modal_exec_error", command=cmd, error=e)
            return ExecResult(exit_code=-1, output=f"Error: {str(e)}")

    @logfire.instrument
    def read_file(self, path: str, channel_id: int = 0) -> str:
        """Read a file from the Modal volume."""
        try:
            volume = self.volumes.get(channel_id)
            if not volume:
                return f"Error: No volume found for channel {channel_id}"

            # Read file from volume
            with volume.read_file(path.lstrip("/")) as f:
                content = f.read().decode("utf-8")
            return content
        except FileNotFoundError:
            logfire.error("modal_read_file_error", path=path, error="File not found")
            return f"Error: File not found: {path}"
        except Exception as e:
            logfire.error("modal_read_file_error", path=path, error=str(e))
            return f"Error reading file: {str(e)}"

    @logfire.instrument
    def write_file(self, path: str, content: str, channel_id: int = 0) -> str:
        """Write a file to the Modal volume."""
        try:
            volume = self.volumes.get(channel_id)
            if not volume:
                return f"Error: No volume found for channel {channel_id}"

            # Write file to volume
            with volume.write_file(path.lstrip("/")) as f:
                f.write(content.encode("utf-8"))
            logfire.info("modal_write_file_success", path=path)
            return f"File written to {path}"
        except Exception as e:
            logfire.error("modal_write_file_error", path=path, error=str(e))
            return f"Error writing file: {str(e)}"

    @logfire.instrument
    def list_dir(self, path: str = "/workspace", channel_id: int = 0, recursive: bool = False) -> str:
        """List files and directories in a path on the Modal volume."""
        try:
            volume = self.volumes.get(channel_id)
            if not volume:
                return f"Error: No volume found for channel {channel_id}"

            # List files in volume (Modal volumes support listdir)
            entries = volume.listdir(path.lstrip("/"), recursive=recursive)

            if not entries:
                return f"Directory {path} is empty"

            result_lines = []
            for entry in sorted(entries):
                if entry.is_dir():
                    result_lines.append(f"d {entry.name}/")
                else:
                    result_lines.append(f"  {entry.name}")

            prefix = path.rstrip("/")
            return "\n".join(f"{prefix}/{line}" if not line.startswith(prefix) else line for line in result_lines)
        except Exception as e:
            logfire.error("modal_list_dir_error", path=path, error=str(e))
            return f"Error listing directory: {str(e)}"

    @logfire.instrument
    def glob_files(self, pattern: str, channel_id: int = 0, path: str = "/workspace") -> str:
        """Find files matching a glob pattern on the Modal volume."""
        try:
            volume = self.volumes.get(channel_id)
            if not volume:
                return f"Error: No volume found for channel {channel_id}"

            # Walk volume and match pattern
            matches = []
            for root, _dirs, files in volume.walk(path.lstrip("/")):
                for f in files:
                    full_path = os.path.join(root, f)
                    if fnmatch.fnmatch(f, pattern) or fnmatch.fnmatch(full_path, pattern):
                        matches.append(full_path)

            if not matches:
                return f"No files matching '{pattern}' in {path}"

            return "\n".join(sorted(matches))
        except Exception as e:
            logfire.error("modal_glob_error", pattern=pattern, error=str(e))
            return f"Error in glob search: {str(e)}"

    @logfire.instrument
    def grep(
        self,
        pattern: str,
        channel_id: int = 0,
        path: str = "/workspace",
        file_glob: str = "**/*",
        case_sensitive: bool = False,
        max_results: int = 50,
    ) -> str:
        """Search for pattern in files on the Modal volume."""
        try:
            volume = self.volumes.get(channel_id)
            if not volume:
                return f"Error: No volume found for channel {channel_id}"

            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)

            # Walk volume and search files
            results: list[FileMatch] = []
            for root, _dirs, files in volume.walk(path.lstrip("/")):
                for f in files:
                    if not fnmatch.fnmatch(f, file_glob.lstrip("/")):
                        continue
                    file_path = os.path.join(root, f)
                    try:
                        with volume.read_file(file_path) as file_handle:
                            content = file_handle.read().decode("utf-8", errors="ignore")
                        for line_num, line in enumerate(content.splitlines(), 1):
                            if regex.search(line):
                                results.append(FileMatch(path=file_path, line_number=line_num, content=line.rstrip()))
                                if len(results) >= max_results:
                                    break
                    except Exception:
                        continue
                    if len(results) >= max_results:
                        break
                if len(results) >= max_results:
                    break

            if not results:
                return f"No matches for '{pattern}' in {path}"

            output_lines = [f"Found {len(results)} match(es) for '{pattern}':"]
            for match in results:
                loc = f"{match.path}:{match.line_number}" if match.line_number else match.path
                content = f" - {match.content}" if match.content else ""
                output_lines.append(f"  {loc}{content}")

            return "\n".join(output_lines)
        except Exception as e:
            logfire.error("modal_grep_error", pattern=pattern, error=str(e))
            return f"Error in grep search: {str(e)}"

    @logfire.instrument
    def find_files(self, name_pattern: str, channel_id: int = 0, path: str = "/workspace") -> str:
        """Find files by name pattern on the Modal volume."""
        try:
            volume = self.volumes.get(channel_id)
            if not volume:
                return f"Error: No volume found for channel {channel_id}"

            matches = []
            for root, _dirs, files in volume.walk(path.lstrip("/")):
                for f in files:
                    if fnmatch.fnmatch(f, name_pattern):
                        matches.append(os.path.join(root, f))
                for d in _dirs:
                    if fnmatch.fnmatch(d, name_pattern):
                        matches.append(os.path.join(root, d) + "/")

            if not matches:
                return f"No files matching '{name_pattern}' in {path}"

            return "\n".join(sorted(matches))
        except Exception as e:
            logfire.error("modal_find_error", name_pattern=name_pattern, error=str(e))
            return f"Error in find: {str(e)}"

    @logfire.instrument
    def make_dir(self, path: str, channel_id: int = 0) -> str:
        """Create a directory on the Modal volume."""
        try:
            volume = self.volumes.get(channel_id)
            if not volume:
                return f"Error: No volume found for channel {channel_id}"

            # Modal volumes don't have mkdir - create a .keep file instead
            keep_path = os.path.join(path.lstrip("/"), ".keep")
            with volume.write_file(keep_path) as f:
                f.write(b"")
            logfire.info("modal_make_dir_success", path=path)
            return f"Directory created: {path}"
        except Exception as e:
            logfire.error("modal_make_dir_error", path=path, error=str(e))
            return f"Error creating directory: {str(e)}"

    @logfire.instrument
    def delete_file(self, path: str, channel_id: int = 0) -> str:
        """Delete a file or directory from the Modal volume."""
        try:
            volume = self.volumes.get(channel_id)
            if not volume:
                return f"Error: No volume found for channel {channel_id}"

            volume.remove_file(path.lstrip("/"))
            logfire.info("modal_delete_success", path=path)
            return f"Path deleted: {path}"
        except FileNotFoundError:
            return f"Error: Path not found: {path}"
        except Exception as e:
            logfire.error("modal_delete_error", path=path, error=str(e))
            return f"Error deleting: {str(e)}"

    @logfire.instrument
    def stop(self, channel_id: int | None = None) -> None:
        """Stop and remove sandboxes. If channel_id is provided, only stop that channel's sandbox."""
        if channel_id is not None:
            if channel_id in self.sandboxes:
                sandbox = self.sandboxes[channel_id]
                sandbox.terminate()
                del self.sandboxes[channel_id]
                logfire.info("modal_sandbox_stopped", channel_id=channel_id)
        else:
            for cid, sandbox in list(self.sandboxes.items()):
                sandbox.terminate()
                logfire.info("modal_sandbox_stopped", channel_id=cid)
            self.sandboxes.clear()
