import asyncio
import contextlib
import fnmatch
import glob as glob_module
import os
import re
import shlex
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import docker
import logfire
import modal
from docker.models.containers import Container


@dataclass
class ExecResult:
    """Result of a sandbox command execution."""
    exit_code: int
    output: str

@dataclass
class FileMatch:
    """Result of a file search."""
    path: str
    line_number: int | None = None
    content: str | None = None

@runtime_checkable
class Sandbox(Protocol):
    """Protocol for a sandboxed execution environment."""
    async def exec_command(self, cmd: str, channel_id: int, timeout: int = 30) -> ExecResult: ...
    async def read_file(self, path: str, channel_id: int) -> str: ...
    async def write_file(self, path: str, content: str, channel_id: int) -> str: ...
    async def edit_file(self, path: str, old_text: str, new_text: str, channel_id: int, occurrence: int = 1) -> str: ...
    async def list_dir(self, path: str, channel_id: int, recursive: bool = False) -> str: ...
    async def glob_files(self, pattern: str, channel_id: int, path: str = "/workspace") -> str: ...
    async def grep_files(self, pattern: str, channel_id: int, path: str = "/workspace", file_glob: str = "**/*", case_sensitive: bool = False, max_results: int = 50) -> str: ...
    async def find_files(self, name_pattern: str, channel_id: int, path: str = "/workspace") -> str: ...
    async def make_dir(self, path: str, channel_id: int) -> str: ...
    async def delete_file(self, path: str, channel_id: int) -> str: ...
    async def stop(self, channel_id: int | None = None) -> None: ...

class DockerSandbox:
    def __init__(self, image: str = "python:3.12", base_workspace: str = "./data/workspaces"):
        self.image = image
        self.base_workspace = os.path.abspath(base_workspace)
        self.containers: dict[int, Container] = {}
        self.client: docker.DockerClient | None = None
        self.denied_commands = frozenset({
            "rm", "rmdir", "docker", "ssh", "scp", "rsync", "sudo", "su", "chmod", "chown", "chgrp",
            "mkfs", "fdisk", "parted", "dd", "iptables", "ip6tables", "ufw", "firewall",
            "systemctl", "service", "init", "shutdown", "reboot",
        })
        os.makedirs(base_workspace, exist_ok=True)
        try:
            self.client = docker.from_env()
            logfire.info("docker_client_initialized")
        except Exception as e:
            logfire.error("docker_not_available", error=str(e))

    def _get_host_path(self, path: str, channel_id: int) -> str:
        workspace_path = os.path.join(self.base_workspace, str(channel_id))
        if path == "/workspace" or path == "/workspace/":
            return workspace_path
        relative_path = path[len("/workspace/") :] if path.startswith("/workspace/") else path.lstrip("/")
        return os.path.join(workspace_path, relative_path)

    def ensure_container(self, channel_id: int) -> Container:
        if not self.client:
            raise Exception("Docker is not available")
        if channel_id in self.containers:
            container = self.containers[channel_id]
            try:
                container.reload()
                if container.status == "running":
                    return container
            except Exception:
                pass
            with contextlib.suppress(Exception):
                container.remove()
            del self.containers[channel_id]

        workspace_path = os.path.join(self.base_workspace, str(channel_id))
        os.makedirs(workspace_path, exist_ok=True)
        container = self.client.containers.run(
            self.image,
            command="sleep infinity",
            detach=True,
            working_dir="/workspace",
            volumes={workspace_path: {"bind": "/workspace", "mode": "rw"}},
            user="1000:1000",
            mem_limit="512m",
            cpu_quota=50000,
            pids_limit=100,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            privileged=False,
        )
        self.containers[channel_id] = container
        return container

    async def exec_command(self, cmd: str, channel_id: int, timeout: int = 30) -> ExecResult:
        cmd_lower = cmd.lower().strip()
        cmd_parts = cmd_lower.split()
        if cmd_parts:
            base_cmd = cmd_parts[0].split("/")[-1]
            if base_cmd in self.denied_commands:
                return ExecResult(exit_code=-1, output=f"Error: Command '{base_cmd}' is not allowed.")

        try:
            container = self.ensure_container(channel_id)
        except Exception as e:
            return ExecResult(exit_code=-1, output=f"Error: {str(e)}")

        try:
            exit_code, output = await asyncio.to_thread(container.exec_run, cmd, workdir="/workspace")
            decoded_output = output.decode("utf-8", errors="ignore") if isinstance(output, bytes) else str(output)
            return ExecResult(exit_code=int(exit_code) if exit_code is not None else -1, output=decoded_output)
        except Exception as e:
            return ExecResult(exit_code=-1, output=f"Error: {str(e)}")


    async def read_file(self, path: str, channel_id: int) -> str:
        host_path = self._get_host_path(path, channel_id)
        try:
            with open(host_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    async def write_file(self, path: str, content: str, channel_id: int) -> str:
        host_path = self._get_host_path(path, channel_id)
        os.makedirs(os.path.dirname(host_path), exist_ok=True)
        try:
            with open(host_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"File written to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    async def edit_file(self, path: str, old_text: str, new_text: str, channel_id: int, occurrence: int = 1) -> str:
        host_path = self._get_host_path(path, channel_id)
        try:
            with open(host_path, encoding="utf-8") as f:
                content = f.read()
            if occurrence == -1:
                new_content = content.replace(old_text, new_text)
                count = content.count(old_text)
            else:
                parts = content.split(old_text)
                if len(parts) <= occurrence:
                    return f"Error: Only {len(parts) - 1} occurrence(s) found."
                new_content = old_text.join(parts[:occurrence]) + new_text + old_text.join(parts[occurrence:])
                count = 1
            with open(host_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"Edited {path}: {count} replacement(s) made"
        except Exception as e:
            return f"Error editing file: {str(e)}"

    async def list_dir(self, path: str, channel_id: int, recursive: bool = False) -> str:
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
                    result_lines.append(f"d {entry}/" if os.path.isdir(full_path) else f"  {entry}")

            prefix = path.rstrip("/")
            return "\n".join(f"{prefix}/{line}" if not line.startswith(prefix) else line for line in result_lines)
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    async def glob_files(self, pattern: str, channel_id: int, path: str = "/workspace") -> str:
        host_path = self._get_host_path(path, channel_id)
        try:
            search_path = os.path.join(host_path, pattern)
            matches = glob_module.glob(search_path, recursive=True)
            rel_matches = [os.path.relpath(m, host_path) for m in sorted(matches)]
            return "\n".join(rel_matches) if rel_matches else f"No files matching '{pattern}' in {path}"
        except Exception as e:
            return f"Error in glob search: {str(e)}"

    async def grep_files(self, pattern: str, channel_id: int, path: str = "/workspace", file_glob: str = "**/*", case_sensitive: bool = False, max_results: int = 50) -> str:
        host_path = self._get_host_path(path, channel_id)
        try:
            flags = 0 if case_sensitive else re.IGNORECASE
            regex = re.compile(pattern, flags)
            search_path = os.path.join(host_path, file_glob)
            files = [f for f in glob_module.glob(search_path, recursive=True) if os.path.isfile(f)]
            results: list[FileMatch] = []
            for file_path in files:
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                results.append(FileMatch(path=os.path.relpath(file_path, host_path), line_number=line_num, content=line.rstrip()))
                                if len(results) >= max_results:
                                    break
                except Exception:
                    continue
                if len(results) >= max_results:
                    break
            if not results:
                return f"No matches for '{pattern}' in {path}"
            output = [f"Found {len(results)} match(es) for '{pattern}':"]
            for m in results:
                output.append(f"  {m.path}:{m.line_number} {m.content}")
            return "\n".join(output)
        except Exception as e:
            return f"Error in grep search: {str(e)}"

    async def find_files(self, name_pattern: str, channel_id: int, path: str = "/workspace") -> str:
        host_path = self._get_host_path(path, channel_id)
        try:
            matches = []
            for root, dirs, files in os.walk(host_path):
                for f in files:
                    if fnmatch.fnmatch(f, name_pattern):
                        matches.append(os.path.relpath(os.path.join(root, f), host_path))
                for d in dirs:
                    if fnmatch.fnmatch(d, name_pattern):
                        matches.append(os.path.relpath(os.path.join(root, d), host_path) + "/")
            return "\n".join(sorted(matches)) if matches else f"No files matching '{name_pattern}' in {path}"
        except Exception as e:
            return f"Error in find: {str(e)}"

    async def make_dir(self, path: str, channel_id: int) -> str:
        host_path = self._get_host_path(path, channel_id)
        try:
            os.makedirs(host_path, exist_ok=True)
            return f"Directory created: {path}"
        except Exception as e:
            return f"Error creating directory: {str(e)}"

    async def delete_file(self, path: str, channel_id: int) -> str:
        host_path = self._get_host_path(path, channel_id)
        try:
            if os.path.isdir(host_path):
                import shutil
                shutil.rmtree(host_path)
            else:
                os.remove(host_path)
            return f"Path deleted: {path}"
        except Exception as e:
            return f"Error deleting: {str(e)}"

    async def stop(self, channel_id: int | None = None) -> None:
        if channel_id is not None:
            if channel_id in self.containers:
                container = self.containers[channel_id]
                container.stop()
                container.remove()
                del self.containers[channel_id]
        else:
            for _cid, container in list(self.containers.items()):
                container.stop()
                container.remove()
            self.containers.clear()

class ModalSandbox:
    def __init__(self, base_volume_name: str = "iter8-bot-workspaces"):
        self.base_volume_name = base_volume_name
        self.sandboxes: dict[int, modal.Sandbox] = {}
        self._app: modal.App | None = None
        self.denied_commands = frozenset({
            "rm", "rmdir", "docker", "ssh", "scp", "rsync", "sudo", "su", "chmod", "chown", "chgrp",
            "mkfs", "fdisk", "parted", "dd", "iptables", "ip6tables", "ufw", "firewall",
            "systemctl", "service", "init", "shutdown", "reboot",
        })

    async def _get_app(self) -> modal.App:
        if self._app is None:
            self._app = await modal.App.lookup.aio("iter8-bot-sandbox", create_if_missing=True)
        return self._app

    async def ensure_sandbox(self, channel_id: int) -> modal.Sandbox:
        if channel_id in self.sandboxes:
            sandbox = self.sandboxes[channel_id]
            try:
                if sandbox.returncode is None:
                    return sandbox
            except Exception:
                pass
            del self.sandboxes[channel_id]

        app = await self._get_app()
        sandbox = await modal.Sandbox.create.aio("python3", "-c", "import time; time.sleep(3600)", app=app, memory=512, cpu=0.5, timeout=3600)
        self.sandboxes[channel_id] = sandbox
        return sandbox

    async def exec_command(self, cmd: str, channel_id: int, timeout: int = 30) -> ExecResult:
        cmd_parts = shlex.split(cmd) if cmd else []
        if cmd_parts:
            base_cmd = cmd_parts[0].split("/")[-1]
            if base_cmd in self.denied_commands:
                return ExecResult(exit_code=-1, output=f"Error: Command '{base_cmd}' is not allowed.")

        sandbox = await self.ensure_sandbox(channel_id)
        try:
            exec_result = await asyncio.to_thread(lambda: sandbox.exec("bash", "-c", cmd, timeout=timeout))
            await exec_result.wait.aio()
            output = await exec_result.stdout.read.aio() if exec_result.stdout else ""
            if exec_result.stderr:
                output += f"\nSTDERR: {await exec_result.stderr.read.aio()}"
            return ExecResult(exit_code=exec_result.returncode or 0, output=output)
        except Exception as e:
            return ExecResult(exit_code=-1, output=f"Error: {str(e)}")

    async def read_file(self, path: str, channel_id: int) -> str:
        result = await self.exec_command(f"cat '{path}'", channel_id)
        return result.output if result.exit_code == 0 else f"Error: {result.output}"

    async def write_file(self, path: str, content: str, channel_id: int) -> str:
        escaped = content.replace("'", "'\\''")
        result = await self.exec_command(f"mkdir -p $(dirname '{path}') && printf '%s' '{escaped}' > '{path}'", channel_id)
        return f"File written to {path}" if result.exit_code == 0 else f"Error: {result.output}"

    async def edit_file(self, path: str, old_text: str, new_text: str, channel_id: int, occurrence: int = 1) -> str:
        import base64
        path_b64, old_b64, new_b64 = [base64.b64encode(x.encode()).decode() for x in (path, old_text, new_text)]
        py = (f'import base64,pathlib; p=pathlib.Path(base64.b64decode("{path_b64}").decode());'
              f'c=p.read_text(); o=base64.b64decode("{old_b64}").decode();'
              f'n=base64.b64decode("{new_b64}").decode(); k={occurrence};'
              f'c=c.replace(o,n,k if k!=-1 else c.count(o)); p.write_text(c)')
        result = await self.exec_command(f"python3 -c '{py}'", channel_id)
        return f"File edited: {path}" if result.exit_code == 0 else f"Error: {result.output}"

    async def list_dir(self, path: str, channel_id: int, recursive: bool = False) -> str:
        cmd = f"ls -laR '{path}'" if recursive else f"ls -la '{path}'"
        result = await self.exec_command(cmd, channel_id)
        return result.output if result.exit_code == 0 else f"Error: {result.output}"

    async def glob_files(self, pattern: str, channel_id: int, path: str = "/workspace") -> str:
        cmd = f"find '{path}' -name '{pattern}' -type f"
        result = await self.exec_command(cmd, channel_id)
        return result.output if result.exit_code == 0 else f"No files matching '{pattern}' in {path}"

    async def grep_files(self, pattern: str, channel_id: int, path: str = "/workspace", file_glob: str = "**/*", case_sensitive: bool = False, max_results: int = 50) -> str:
        flags = "" if case_sensitive else "-i"
        cmd = f"grep -rn {flags} '{pattern}' '{path}' --include='{file_glob}' | head -n {max_results}"
        result = await self.exec_command(cmd, channel_id)
        return result.output if result.exit_code == 0 else f"No matches for '{pattern}' in {path}"

    async def find_files(self, name_pattern: str, channel_id: int, path: str = "/workspace") -> str:
        cmd = f"find '{path}' -name '{name_pattern}'"
        result = await self.exec_command(cmd, channel_id)
        return result.output if result.exit_code == 0 else f"No files matching '{name_pattern}' in {path}"

    async def make_dir(self, path: str, channel_id: int) -> str:
        result = await self.exec_command(f"mkdir -p '{path}'", channel_id)
        return f"Directory created: {path}" if result.exit_code == 0 else f"Error: {result.output}"

    async def delete_file(self, path: str, channel_id: int) -> str:
        result = await self.exec_command(f"rm -rf '{path}'", channel_id)
        return f"Path deleted: {path}" if result.exit_code == 0 else f"Error: {result.output}"

    async def stop(self, channel_id: int | None = None) -> None:
        if channel_id is not None:
            if channel_id in self.sandboxes:
                self.sandboxes[channel_id].terminate()
                del self.sandboxes[channel_id]
        else:
            for sandbox in self.sandboxes.values():
                sandbox.terminate()
            self.sandboxes.clear()

class SandboxManager:
    """Factory and coordinator for sandboxed environments."""
    def __init__(self) -> None:
        self._docker = DockerSandbox()
        self._modal = ModalSandbox()

    def get_sandbox(self) -> Sandbox:
        """Return the best available sandbox (Prefer Docker for latency)."""
        if self._docker.client:
            return self._docker
        if True: # Modal is always "available" until it fails
            return self._modal
        raise RuntimeError("No sandbox available")
