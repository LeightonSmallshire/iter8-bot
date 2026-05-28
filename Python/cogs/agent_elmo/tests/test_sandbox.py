import pytest
import asyncio
import os
import tempfile
from unittest.mock import MagicMock, patch, AsyncMock
from cogs.agent_elmo.sandbox.manager import SandboxManager, DockerSandbox, ModalSandbox, ExecResult

@pytest.fixture
def mock_docker_client():
    with patch("docker.from_env") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

@pytest.mark.asyncio
async def test_docker_sandbox_exec(mock_docker_client) -> None:
    sandbox = DockerSandbox()
    sandbox.client = mock_docker_client
    mock_container = MagicMock()
    mock_container.exec_run.return_value = (0, b"Hello Docker")
    mock_docker_client.containers.run.return_value = mock_container
    result = await sandbox.exec_command("echo Hello", channel_id=123)
    assert result.exit_code == 0
    assert "Hello Docker" in result.output

@pytest.mark.asyncio
async def test_docker_sandbox_denied_command() -> None:
    sandbox = DockerSandbox()
    result = await sandbox.exec_command("rm -rf /", channel_id=123)
    assert result.exit_code == -1
    assert "not allowed" in result.output

@pytest.mark.asyncio
async def test_docker_sandbox_no_client() -> None:
    sandbox = DockerSandbox()
    sandbox.client = None
    result = await sandbox.exec_command("echo Hello", channel_id=123)
    assert "Docker is not available" in result.output

@pytest.mark.asyncio
async def test_docker_sandbox_exec_error(mock_docker_client) -> None:
    sandbox = DockerSandbox()
    sandbox.client = mock_docker_client
    mock_container = MagicMock()
    mock_container.exec_run.side_effect = Exception("Docker Error")
    mock_docker_client.containers.run.return_value = mock_container
    result = await sandbox.exec_command("echo Hello", channel_id=123)
    assert result.exit_code == -1
    assert "Error: Docker Error" in result.output

@pytest.mark.asyncio
async def test_modal_sandbox_exec() -> None:
    with patch("modal.App.lookup") as mock_lookup:
        mock_app = MagicMock()
        mock_lookup.return_value = mock_app
        with patch("modal.Sandbox.create") as mock_create:
            mock_sandbox = MagicMock()
            mock_sandbox.exec.return_value = MagicMock()
            mock_sandbox.exec.return_value.wait = MagicMock()
            mock_sandbox.exec.return_value.stdout.read.return_value = "Hello Modal"
            mock_sandbox.exec.return_value.returncode = 0
            mock_create.return_value = mock_sandbox
            manager = ModalSandbox()
            result = await manager.exec_command("echo Hello", channel_id=123)
            assert result.exit_code == 0
            assert "Hello Modal" in result.output

@pytest.mark.asyncio
async def test_modal_sandbox_exec_error():
    with patch("modal.App.lookup") as mock_lookup:
        mock_lookup.return_value = MagicMock()
        with patch("modal.Sandbox.create") as mock_create:
            mock_sandbox = MagicMock()
            mock_sandbox.exec.side_effect = Exception("Modal Error")
            mock_create.return_value = mock_sandbox
            manager = ModalSandbox()
            result = await manager.exec_command("echo Hello", channel_id=123)
            assert result.exit_code == -1
            assert "Error: Modal Error" in result.output

def test_sandbox_manager_preference() -> None:
    manager = SandboxManager()
    manager._docker.client = MagicMock()
    assert isinstance(manager.get_sandbox(), DockerSandbox)
    manager._docker.client = None
    assert isinstance(manager.get_sandbox(), ModalSandbox)

@pytest.mark.asyncio
async def test_docker_sandbox_file_ops(mock_docker_client) -> None:
    sandbox = DockerSandbox()
    sandbox.client = mock_docker_client
    mock_container = MagicMock()
    mock_docker_client.containers.run.return_value = mock_container
    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox.base_workspace = tmpdir
        await sandbox.write_file("/workspace/test.txt", "hello", channel_id=123)
        with open(os.path.join(tmpdir, "123/test.txt"), "r") as f:
            assert f.read() == "hello"
        res = await sandbox.read_file("/workspace/test.txt", channel_id=123)
        assert res == "hello"
        await sandbox.edit_file("/workspace/test.txt", "hello", "world", channel_id=123)
        with open(os.path.join(tmpdir, "123/test.txt"), "r") as f:
            assert f.read() == "world"
        await sandbox.make_dir("/workspace/newdir", channel_id=123)
        assert os.path.isdir(os.path.join(tmpdir, "123/newdir"))
        res = await sandbox.list_dir("/workspace", channel_id=123)
        assert "test.txt" in res
        assert "newdir" in res
        await sandbox.delete_file("/workspace/test.txt", channel_id=123)
        assert not os.path.exists(os.path.join(tmpdir, "123/test.txt"))

@pytest.mark.asyncio
async def test_modal_sandbox_file_ops():
    with patch("modal.App.lookup") as mock_lookup:
        mock_lookup.return_value = MagicMock()
        with patch("modal.Sandbox.create") as mock_create:
            mock_sandbox = MagicMock()
            mock_sandbox.exec.return_value = MagicMock()
            mock_sandbox.exec.return_value.wait = MagicMock()
            mock_sandbox.exec.return_value.stdout.read.return_value = "success"
            mock_sandbox.exec.return_value.returncode = 0
            mock_create.return_value = mock_sandbox
            manager = ModalSandbox()
            assert "success" in await manager.read_file("path", 123)
            assert "File written" in await manager.write_file("path", "content", 123)
            assert "File edited" in await manager.edit_file("path", "old", "new", 123)
            assert "success" in await manager.list_dir("path", 123)
            assert "success" in await manager.glob_files("pattern", 123)
            assert "success" in await manager.grep_files("pattern", 123)
            assert "success" in await manager.find_files("pattern", 123)
            assert "Directory created" in await manager.make_dir("path", 123)
            manager.denied_commands = set()
            assert "Path deleted" in await manager.delete_file("path", 123)

@pytest.mark.asyncio
async def test_sandbox_stop():
    docker = DockerSandbox()
    docker.client = MagicMock()
    mock_container = MagicMock()
    docker.containers[123] = mock_container
    await docker.stop(123)
    assert 123 not in docker.containers
    modal = ModalSandbox()
    mock_sandbox = MagicMock()
    modal.sandboxes[123] = mock_sandbox
    await modal.stop(123)
    assert 123 not in modal.sandboxes
