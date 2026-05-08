"""Modal-based sandbox manager - replaces DockerManager for secure code execution.

Uses Modal (https://modal.com) for serverless sandboxed code execution.
Free tier: $30/mo recurring credits.

Interface matches DockerManager for drop-in replacement.
"""
import fnmatch
import os
import re
import shlex
from dataclasses import dataclass
from typing import Any

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
    Each channel gets its own Modal sandbox.
    """

    def __init__(self, base_volume_name: str = "iter8-bot-workspaces"):
        self.base_volume_name: str = base_volume_name
        self.sandboxes: dict[int, modal.Sandbox] = {}  # channel_id -> sandbox
        self._app = None

        # Security: Command denylist - dangerous commands that should never execute
        self.denied_commands: frozenset[str] = frozenset(
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

    def _get_app(self) -> modal.App:
        """Get or create the Modal App for sandboxes."""
        if self._app is None:
            self._app = modal.App.lookup("iter8-bot-sandbox", create_if_missing=True)
            logfire.info("modal_app_initialized")
        return self._app

    @logfire.instrument
    def ensure_sandbox(self, channel_id: int) -> modal.Sandbox:
        """Ensure a Modal sandbox is running for the given channel."""
        if channel_id in self.sandboxes:
            sandbox = self.sandboxes[channel_id]
            # Check if sandbox is still running
            try:
                if sandbox.returncode is None:  # Still running
                    return sandbox
            except Exception:
                pass
            # Remove dead sandbox
            del self.sandboxes[channel_id]

        # Create a new sandbox
        app = self._get_app()
        sandbox = modal.Sandbox.create(
            "python3",
            "-c",
            "import time; time.sleep(3600)",  # Keep alive for 1 hour
            app=app,
            # Resource limits
            memory=512,  # MB
            cpu=0.5,  # vCPU
            timeout=3600,  # 1 hour max
        )
        self.sandboxes[channel_id] = sandbox
        logfire.info("modal_sandbox_started", channel_id=channel_id)
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
        cmd_parts = shlex.split(cmd) if cmd else []
        if cmd_parts:
            base_cmd = cmd_parts[0].split("/")[-1]  # Handle /usr/bin/rm style
            if base_cmd in self.denied_commands:
                logfire.warn("modal_exec_denied", command=cmd[:100], reason="denied_command")
                return ExecResult(
                    exit_code=-1, output=f"Error: Command '{base_cmd}' is not allowed for security reasons."
                )

        sandbox = self.ensure_sandbox(channel_id)
        try:
            # Execute command via bash -c
            exec_result = sandbox.exec("bash", "-c", cmd, timeout=timeout)

            # Wait for command to complete
            exec_result.wait()

            output = exec_result.stdout.read() if exec_result.stdout else ""
            if exec_result.stderr:
                stderr_output = exec_result.stderr.read()
                output += f"\nSTDERR: {stderr_output}"

            exit_code = exec_result.returncode if exec_result.returncode else 0
            return ExecResult(exit_code=exit_code, output=output)
        except Exception as e:
            logfire.error("modal_exec_error", command=cmd, error=e)
            return ExecResult(exit_code=-1, output=f"Error: {str(e)}")

    @logfire.instrument
    def read_file(self, path: str, channel_id: int = 0) -> str:
        """Read a file from the sandbox."""
        result = self.exec_command(f"cat '{path}'", channel_id=channel_id, timeout=10)
        if result.exit_code != 0:
            return f"Error: Failed to read file: {result.output}"
        return result.output

    @logfire.instrument
    def write_file(self, path: str, content: str, channel_id: int = 0) -> str:
        """Write a file to the sandbox."""
        # Escape single quotes in content for shell
        escaped = content.replace("'", "'\\''")
        result = self.exec_command(
            f"mkdir -p $(dirname '{path}') && printf '%s' '{escaped}' > '{path}'",
            channel_id=channel_id,
            timeout=10
        )
        if result.exit_code != 0:
            return f"Error: Failed to write file: {result.output}"
        logfire.info("modal_write_file_success", path=path)
        return f"File written to {path}"

    @logfire.instrument
    def list_dir(self, path: str = "/workspace", channel_id: int = 0, recursive: bool = False) -> str:
        """List files and directories in a path on the sandbox."""
        cmd = f"ls -laR '{path}'" if recursive else f"ls -la '{path}'"
        result = self.exec_command(cmd, channel_id=channel_id, timeout=10)
        if result.exit_code != 0:
            return f"Error listing directory: {result.output}"
        return result.output

    @logfire.instrument
    def glob_files(self, pattern: str, channel_id: int = 0, path: str = "/workspace") -> str:
        """Find files matching a glob pattern on the sandbox."""
        cmd = f"find '{path}' -name '{pattern}' -type f"
        result = self.exec_command(cmd, channel_id=channel_id, timeout=10)
        if result.exit_code != 0 or not result.output.strip():
            return f"No files matching '{pattern}' in {path}"
        matches = [line for line in result.output.splitlines() if line.strip()]
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        return "\n".join(matches)

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
        """Search for pattern in files on the sandbox."""
        flags = "" if case_sensitive else "-i"
        cmd = f"grep -rn {flags} '{pattern}' '{path}' --include='{file_glob}' | head -n {max_results}"
        result = self.exec_command(cmd, channel_id=channel_id, timeout=30)
        if result.exit_code != 0 or not result.output.strip():
            return f"No matches for '{pattern}' in {path}"

        lines = [line for line in result.output.strip().split("\n") if line.strip()]
        if not lines:
            return f"No matches for '{pattern}' in {path}"

        output_lines = [f"Found {len(lines)} match(es) for '{pattern}':"]
        output_lines.extend(f"  {line}" for line in lines[:max_results])
        return "\n".join(output_lines)

    @logfire.instrument
    def find_files(self, name_pattern: str, channel_id: int = 0, path: str = "/workspace") -> str:
        """Find files by name pattern on the sandbox."""
        cmd = f"find '{path}' -name '{name_pattern}'"
        result = self.exec_command(cmd, channel_id=channel_id, timeout=10)
        if result.exit_code != 0:
            return f"No files matching '{name_pattern}' in {path}"
        matches = [line for line in result.output.splitlines() if line.strip()]
        if not matches:
            return f"No files matching '{name_pattern}' in {path}"
        return "\n".join(sorted(matches))

    @logfire.instrument
    def make_dir(self, path: str, channel_id: int = 0) -> str:
        """Create a directory on the sandbox."""
        result = self.exec_command(f"mkdir -p '{path}'", channel_id=channel_id, timeout=10)
        if result.exit_code != 0:
            return f"Error: Failed to create directory: {result.output}"
        logfire.info("modal_make_dir_success", path=path)
        return f"Directory created: {path}"

    @logfire.instrument
    def delete_file(self, path: str, channel_id: int = 0) -> str:
        """Delete a file or directory from the sandbox."""
        result = self.exec_command(f"rm -rf '{path}'", channel_id=channel_id, timeout=10)
        if result.exit_code != 0:
            return f"Error: Failed to delete: {result.output}"
        logfire.info("modal_delete_success", path=path)
        return f"Path deleted: {path}"

    @logfire.instrument
    def stop(self, channel_id: int | None = None) -> None:
        """Stop and remove sandboxes. If channel_id is provided, only stop that channel's sandbox."""
        if channel_id is not None:
            if channel_id in self.sandboxes:
                sandbox = self.sandboxes[channel_id]
                try:
                    sandbox.terminate()
                    logfire.info("modal_sandbox_stopped", channel_id=channel_id)
                except Exception as e:
                    logfire.error("modal_stop_error", channel_id=channel_id, error=str(e))
                del self.sandboxes[channel_id]
        else:
            for cid in list(self.sandboxes.keys()):
                sandbox = self.sandboxes[cid]
                try:
                    sandbox.terminate()
                    logfire.info("modal_sandbox_stopped", channel_id=cid)
                except Exception as e:
                    logfire.error("modal_stop_error", channel_id=cid, error=str(e))
            self.sandboxes.clear()
