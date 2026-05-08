import contextlib
import fnmatch
import glob as glob_module
import os
import re
from dataclasses import dataclass
from typing import Any

import docker
import logfire
from docker.models.containers import Container


@dataclass
class ExecResult:
    """Result of a Docker command execution."""

    exit_code: int
    output: str


@dataclass
class FileMatch:
    """Result of a file search."""

    path: str
    line_number: int | None = None
    content: str | None = None


class DockerManager:
    def __init__(self, image: str = "python:3.12", base_workspace: str = "./data/workspaces"):
        self.image: str = image
        self.base_workspace: str = os.path.abspath(base_workspace)
        self.containers: dict[int, Container] = {}  # channel_id -> container
        self.client: docker.DockerClient | None = None

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

        # Ensure base workspace directory exists
        os.makedirs(base_workspace, exist_ok=True)

        try:
            self.client = docker.from_env()
            logfire.info("docker_client_initialized")
        except Exception as e:
            logfire.error("docker_not_available", error=str(e))
            print(f"Warning: Docker not available - {e}")

    def ensure_container(self, channel_id: int) -> Container:
        """Ensure a container is running for the given channel."""
        if not self.client:
            raise Exception("Docker is not available")

        # Check if container for this channel exists and is running
        if channel_id in self.containers:
            container = self.containers[channel_id]
            try:
                container.reload()
                if container.status == "running":
                    return container
            except Exception:
                # Container might have been removed
                pass
            # Container exists but not running or can't reload, remove it
            with contextlib.suppress(Exception):
                container.remove()
            del self.containers[channel_id]

        with logfire.span("docker_ensure_container", image=self.image, channel_id=channel_id):
            # Create workspace directory for this channel
            workspace_path = os.path.join(self.base_workspace, str(channel_id))
            os.makedirs(workspace_path, exist_ok=True)

            # Create and start a new container with channel-specific volume and security hardening
            container = self.client.containers.run(
                self.image,
                command="sleep infinity",
                detach=True,
                working_dir="/workspace",
                volumes={workspace_path: {"bind": "/workspace", "mode": "rw"}},
                # Security: Run as non-root user
                user="1000:1000",
                # Security: Resource limits
                mem_limit="512m",
                cpu_quota=50000,  # 50% of one CPU
                pids_limit=100,  # Limit number of processes
                # Security: Drop all capabilities
                cap_drop=["ALL"],
                # Security: No privilege escalation
                security_opt=["no-new-privileges"],
                # Security: Not privileged mode
                privileged=False,
            )
            assert container is not None
            container_id: str = str(container.id) if container.id else "unknown"
            self.containers[channel_id] = container
            logfire.info("docker_container_started", container_id=container_id[:12], channel_id=channel_id)
            return container

    def __enter__(self) -> "DockerManager":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    def exec_command(self, cmd: str, channel_id: int = 0, timeout: int = 30) -> ExecResult:
        """Execute a command in the container for the given channel.

        Args:
            cmd: Command to execute
            channel_id: Channel ID for container workspace
            timeout: Maximum seconds to wait for command completion (default: 30)
        """
        with logfire.span("docker_exec", command=cmd, channel_id=channel_id):
            # Security: Check for denied commands
            cmd_lower = cmd.lower().strip()
            cmd_parts = cmd_lower.split()
            if cmd_parts:
                base_cmd = cmd_parts[0].split("/")[-1]  # Handle /usr/bin/rm style
                if base_cmd in self.denied_commands:
                    logfire.warn("docker_exec_denied", command=cmd[:100], reason="denied_command")
                    return ExecResult(
                        exit_code=-1, output=f"Error: Command '{base_cmd}' is not allowed for security reasons."
                    )

            container = self.ensure_container(channel_id)
            try:
                exit_code, output = container.exec_run(cmd, workdir="/workspace", timeout=timeout)
                decoded_output: str = (
                    output.decode("utf-8", errors="ignore") if isinstance(output, bytes) else str(output)
                )
                logfire.debug(
                    "docker_exec_result", exit_code=exit_code, output=decoded_output, output_length=len(decoded_output)
                )
                exit_code_int = int(exit_code) if exit_code is not None else -1
                return ExecResult(exit_code=exit_code_int, output=decoded_output)
            except Exception as e:
                logfire.error("docker_exec_error", command=cmd, error=e)
                return ExecResult(exit_code=-1, output=f"Error: {str(e)}")

    def _get_host_path(self, path: str, channel_id: int) -> str:
        """Convert a container path to host path."""
        workspace_path = os.path.join(self.base_workspace, str(channel_id))
        # Handle /workspace with or without trailing slash
        if path == "/workspace" or path == "/workspace/":
            return workspace_path
        relative_path = path[len("/workspace/") :] if path.startswith("/workspace/") else path.lstrip("/")
        return os.path.join(workspace_path, relative_path)

    def read_file(self, path: str, channel_id: int = 0) -> str:
        """Read a file from the host workspace directory (mounted as /workspace in container)."""
        with logfire.span("docker_read_file", path=path, channel_id=channel_id):
            host_path = self._get_host_path(path, channel_id)
            try:
                with open(host_path, encoding="utf-8") as f:
                    content = f.read()
                logfire.debug("docker_read_file_success", path=path, content_length=len(content))
                return content
            except FileNotFoundError:
                logfire.error("docker_read_file_error", path=path, error="File not found")
                return f"Error: File not found: {path}"
            except Exception as e:
                logfire.error("docker_read_file_error", path=path, error=str(e))
                return f"Error reading file: {str(e)}"

    def edit_file(self, path: str, old_text: str, new_text: str, channel_id: int = 0, occurrence: int = 1) -> str:
        """Edit a file by replacing old_text with new_text.

        Args:
            path: File path (e.g., /workspace/file.txt)
            old_text: Text to search for and replace
            new_text: Text to replace with
            channel_id: Channel ID for container workspace
            occurrence: Which occurrence to replace (1-based, -1 for all)

        Returns:
            Success/error message
        """
        with logfire.span("docker_edit_file", path=path, channel_id=channel_id, occurrence=occurrence):
            host_path = self._get_host_path(path, channel_id)
            try:
                with open(host_path, encoding="utf-8") as f:
                    content = f.read()

                if occurrence == -1:
                    # Replace all occurrences
                    new_content = content.replace(old_text, new_text)
                    count = content.count(old_text)
                else:
                    # Replace specific occurrence
                    parts = content.split(old_text)
                    if len(parts) <= occurrence:
                        return f"Error: Only {len(parts) - 1} occurrence(s) found, requested {occurrence}"
                    new_content = old_text.join(parts[:occurrence]) + new_text + old_text.join(parts[occurrence:])
                    count = 1

                with open(host_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                logfire.info("docker_edit_file_success", path=path, replacements=count)
                return f"Edited {path}: {count} replacement(s) made"
            except FileNotFoundError:
                return f"Error: File not found: {path}"
            except Exception as e:
                logfire.error("docker_edit_file_error", path=path, error=str(e))
                return f"Error editing file: {str(e)}"

    def write_file(self, path: str, content: str, channel_id: int = 0) -> str:
        """Write a file to the host workspace directory (mounted as /workspace in container)."""
        with logfire.span("docker_write_file", path=path, content_length=len(content), channel_id=channel_id):
            host_path = self._get_host_path(path, channel_id)
            os.makedirs(os.path.dirname(host_path), exist_ok=True)
            try:
                with open(host_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logfire.info("docker_write_file_success", path=path)
                return f"File written to {path}"
            except Exception as e:
                logfire.error("docker_write_file_error", path=path, error=str(e))
                return f"Error writing file: {str(e)}"

    def list_dir(self, path: str = "/workspace", channel_id: int = 0, recursive: bool = False) -> str:
        """List files and directories in a path.

        Args:
            path: Directory path to list
            channel_id: Channel ID for container workspace
            recursive: If True, list recursively

        Returns:
            Formatted string of files/directories
        """
        with logfire.span("docker_list_dir", path=path, recursive=recursive, channel_id=channel_id):
            host_path = self._get_host_path(path, channel_id)
            try:
                if not os.path.exists(host_path):
                    return f"Error: Path not found: {path}"

                result_lines = []
                if recursive:
                    for root, dirs, files in os.walk(host_path):
                        rel_root = os.path.relpath(root, host_path)
                        if rel_root == ".":
                            rel_root = ""
                        for d in sorted(dirs):
                            result_lines.append(f"d {os.path.join(rel_root, d)}/")
                        for f in sorted(files):
                            result_lines.append(f"  {os.path.join(rel_root, f)}")
                else:
                    entries = os.listdir(host_path)
                    for entry in sorted(entries):
                        full_path = os.path.join(host_path, entry)
                        if os.path.isdir(full_path):
                            result_lines.append(f"d {entry}/")
                        else:
                            result_lines.append(f"  {entry}")

                if not result_lines:
                    return f"Directory {path} is empty"

                prefix = path.rstrip("/")
                return "\n".join(f"{prefix}/{line}" if not line.startswith(prefix) else line for line in result_lines)
            except Exception as e:
                logfire.error("docker_list_dir_error", path=path, error=str(e))
                return f"Error listing directory: {str(e)}"

    def glob_files(self, pattern: str, channel_id: int = 0, path: str = "/workspace") -> str:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "**/*.py")
            channel_id: Channel ID for container workspace
            path: Base path to search from

        Returns:
            Formatted string of matching files
        """
        with logfire.span("docker_glob", pattern=pattern, path=path, channel_id=channel_id):
            host_path = self._get_host_path(path, channel_id)
            try:
                search_path = os.path.join(host_path, pattern)
                matches = glob_module.glob(search_path, recursive=True)

                if not matches:
                    return f"No files matching '{pattern}' in {path}"

                # Convert to relative paths
                rel_matches = [os.path.relpath(m, host_path) for m in sorted(matches)]
                return "\n".join(rel_matches)
            except Exception as e:
                logfire.error("docker_glob_error", pattern=pattern, error=str(e))
                return f"Error in glob search: {str(e)}"

    def grep(
        self,
        pattern: str,
        channel_id: int = 0,
        path: str = "/workspace",
        file_glob: str = "**/*",
        case_sensitive: bool = False,
        max_results: int = 50,
    ) -> str:
        """Search for pattern in files.

        Args:
            pattern: Regex pattern to search for
            channel_id: Channel ID for container workspace
            path: Base path to search
            file_glob: Glob pattern for files to search (e.g., "**/*.py")
            case_sensitive: Whether search is case sensitive
            max_results: Maximum number of results to return

        Returns:
            Formatted string of matches with file paths and line numbers
        """
        with logfire.span("docker_grep", pattern=pattern, path=path, file_glob=file_glob, channel_id=channel_id):
            host_path = self._get_host_path(path, channel_id)
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                regex = re.compile(pattern, flags)

                # Find files to search
                search_path = os.path.join(host_path, file_glob)
                files = glob_module.glob(search_path, recursive=True)
                files = [f for f in files if os.path.isfile(f)]

                results: list[FileMatch] = []
                for file_path in files:
                    try:
                        with open(file_path, encoding="utf-8", errors="ignore") as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    rel_path = os.path.relpath(file_path, host_path)
                                    results.append(
                                        FileMatch(path=rel_path, line_number=line_num, content=line.rstrip())
                                    )
                                    if len(results) >= max_results:
                                        break
                    except Exception:
                        continue
                    if len(results) >= max_results:
                        break

                if not results:
                    return f"No matches for '{pattern}' in {path}"

                # Format results
                output_lines = [f"Found {len(results)} match(es) for '{pattern}':"]
                for match in results:
                    loc = f"{match.path}:{match.line_number}" if match.line_number else match.path
                    content = f" - {match.content}" if match.content else ""
                    output_lines.append(f"  {loc}{content}")

                return "\n".join(output_lines)
            except Exception as e:
                logfire.error("docker_grep_error", pattern=pattern, error=str(e))
                return f"Error in grep search: {str(e)}"

    def find_files(self, name_pattern: str, channel_id: int = 0, path: str = "/workspace") -> str:
        """Find files by name pattern.

        Args:
            name_pattern: Pattern to match filename (e.g., "*.py" or "test_*.py")
            channel_id: Channel ID for container workspace
            path: Base path to search

        Returns:
            Formatted string of matching files
        """
        with logfire.span("docker_find", name_pattern=name_pattern, path=path, channel_id=channel_id):
            host_path = self._get_host_path(path, channel_id)
            try:
                matches = []
                for root, dirs, files in os.walk(host_path):
                    for f in files:
                        if fnmatch.fnmatch(f, name_pattern):
                            rel_path = os.path.relpath(os.path.join(root, f), host_path)
                            matches.append(rel_path)
                    for d in dirs:
                        if fnmatch.fnmatch(d, name_pattern):
                            rel_path = os.path.relpath(os.path.join(root, d), host_path)
                            matches.append(rel_path + "/")

                if not matches:
                    return f"No files matching '{name_pattern}' in {path}"

                return "\n".join(sorted(matches))
            except Exception as e:
                logfire.error("docker_find_error", name_pattern=name_pattern, error=str(e))
                return f"Error in find: {str(e)}"

    def make_dir(self, path: str, channel_id: int = 0) -> str:
        """Create a directory.

        Args:
            path: Directory path to create
            channel_id: Channel ID for container workspace

        Returns:
            Success/error message
        """
        with logfire.span("docker_make_dir", path=path, channel_id=channel_id):
            host_path = self._get_host_path(path, channel_id)
            try:
                os.makedirs(host_path, exist_ok=True)
                logfire.info("docker_make_dir_success", path=path)
                return f"Directory created: {path}"
            except Exception as e:
                logfire.error("docker_make_dir_error", path=path, error=str(e))
                return f"Error creating directory: {str(e)}"

    def delete_file(self, path: str, channel_id: int = 0) -> str:
        """Delete a file or directory.

        Args:
            path: Path to delete
            channel_id: Channel ID for container workspace

        Returns:
            Success/error message
        """
        with logfire.span("docker_delete", path=path, channel_id=channel_id):
            host_path = self._get_host_path(path, channel_id)
            try:
                if os.path.isdir(host_path):
                    import shutil

                    shutil.rmtree(host_path)
                    logfire.info("docker_delete_dir_success", path=path)
                    return f"Directory deleted: {path}"
                else:
                    os.remove(host_path)
                    logfire.info("docker_delete_file_success", path=path)
                    return f"File deleted: {path}"
            except FileNotFoundError:
                return f"Error: Path not found: {path}"
            except Exception as e:
                logfire.error("docker_delete_error", path=path, error=str(e))
                return f"Error deleting: {str(e)}"

    def stop(self, channel_id: int | None = None) -> None:
        """Stop and remove containers. If channel_id is provided, only stop that channel's container."""
        if channel_id is not None:
            # Stop specific channel container
            if channel_id in self.containers:
                container = self.containers[channel_id]
                container_id_str = str(container.id) if container.id else "unknown"
                with logfire.span("docker_stop_container", container_id=container_id_str[:12], channel_id=channel_id):
                    container.stop()
                    container.remove()
                    del self.containers[channel_id]
                    logfire.info("docker_container_stopped", channel_id=channel_id)
        else:
            # Stop all containers
            for cid, container in list(self.containers.items()):
                container_id_str = str(container.id) if container.id else "unknown"
                with logfire.span("docker_stop_container", container_id=container_id_str[:12], channel_id=cid):
                    container.stop()
                    container.remove()
                    logfire.info("docker_container_stopped", channel_id=cid)
            self.containers.clear()
