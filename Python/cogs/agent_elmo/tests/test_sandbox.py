import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cogs.agent_elmo.sandbox.manager import DockerSandbox, ModalSandbox, SandboxManager


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
async def test_docker_sandbox_container_lifecycle(mock_docker_client) -> None:
    sandbox = DockerSandbox()
    sandbox.client = mock_docker_client
    mock_container = MagicMock()
    mock_container.status = "running"
    mock_docker_client.containers.run.return_value = mock_container

    # 1. Create
    c1 = sandbox.ensure_container(123)
    assert c1 == mock_container
    assert 123 in sandbox.containers

    # 2. Reload (Success)
    sandbox.ensure_container(123)
    mock_container.reload.assert_called()

    # 3. Reload (Failed/Stopped)
    mock_container.status = "exited"
    sandbox.ensure_container(123)
    mock_container.remove.assert_called()
    assert mock_docker_client.containers.run.call_count == 2

@pytest.mark.asyncio
async def test_modal_sandbox_exec() -> None:
    with patch("cogs.agent_elmo.sandbox.manager.modal.App.lookup.aio", new_callable=AsyncMock) as mock_lookup:
        mock_lookup.return_value = MagicMock()
        with patch("cogs.agent_elmo.sandbox.manager.modal.Sandbox.create.aio", new_callable=AsyncMock) as mock_create:
            mock_sandbox = MagicMock()
            mock_create.return_value = mock_sandbox
            exec_result = MagicMock()
            exec_result.wait.aio = AsyncMock()
            exec_result.stdout.read.aio = AsyncMock(return_value="Hello Modal")
            exec_result.stderr = None
            exec_result.returncode = 0
            mock_sandbox.exec.return_value = exec_result
            manager = ModalSandbox()
            result = await manager.exec_command("echo Hello", channel_id=123)
            assert result.exit_code == 0
            assert "Hello Modal" in result.output

@pytest.mark.asyncio
async def test_modal_sandbox_denied_command() -> None:
    manager = ModalSandbox()
    result = await manager.exec_command("rm -rf /", channel_id=123)
    assert result.exit_code == -1
    assert "not allowed" in result.output

@pytest.mark.asyncio
async def test_modal_sandbox_exec_error():
    with patch("modal.App.lookup") as mock_lookup:
        mock_lookup.aio = AsyncMock(return_value=MagicMock())
        with patch("modal.Sandbox.create") as mock_create:
            mock_sandbox = MagicMock()
            mock_create.aio = AsyncMock(return_value=mock_sandbox)
            exec_result = MagicMock()
            exec_result.wait.aio = AsyncMock()
            exec_result.stdout.read.aio = AsyncMock()
            exec_result.stderr = None
            mock_sandbox.exec.return_value = exec_result
            mock_sandbox.exec.side_effect = Exception("Modal Error")
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
        # Test write
        await sandbox.write_file("/workspace/test.txt", "hello", channel_id=123)
        assert os.path.exists(os.path.join(tmpdir, "123/test.txt"))

        # Test read
        res = await sandbox.read_file("/workspace/test.txt", channel_id=123)
        assert res == "hello"

        # Test read error
        res = await sandbox.read_file("/workspace/missing.txt", channel_id=123)
        assert "Error reading file" in res

        # Test edit (occurrence 1)
        await sandbox.edit_file("/workspace/test.txt", "hello", "world", channel_id=123, occurrence=1)
        with open(os.path.join(tmpdir, "123/test.txt")) as f:
            assert f.read() == "world"

        # Test edit (occurrence -1 / replace all)
        await sandbox.write_file("/workspace/test.txt", "a b a", channel_id=123)
        await sandbox.edit_file("/workspace/test.txt", "a", "x", channel_id=123, occurrence=-1)
        with open(os.path.join(tmpdir, "123/test.txt")) as f:
            assert f.read() == "x b x"

        # Test edit error (not found)
        res = await sandbox.edit_file("/workspace/test.txt", "missing", "found", channel_id=123, occurrence=1)
        assert "Error: Only 0 occurrence(s) found" in res

        # Test edit exception
        with patch("builtins.open", side_effect=Exception("Open Fail")):
            res = await sandbox.edit_file("/workspace/test.txt", "a", "b", channel_id=123)
            assert "Error editing file: Open Fail" in res

        # Test make_dir
        await sandbox.make_dir("/workspace/dir1/dir2", channel_id=123)
        assert os.path.isdir(os.path.join(tmpdir, "123/dir1/dir2"))

        # Test delete_file (file)
        await sandbox.delete_file("/workspace/test.txt", channel_id=123)
        assert not os.path.exists(os.path.join(tmpdir, "123/test.txt"))

        # Test delete_file (dir)
        await sandbox.delete_file("/workspace/dir1", channel_id=123)
        assert not os.path.exists(os.path.join(tmpdir, "123/dir1"))

        # Test delete_file error
        res = await sandbox.delete_file("/workspace/ghost", channel_id=123)
        assert "Error deleting" in res

@pytest.mark.asyncio
async def test_docker_sandbox_dir_ops(mock_docker_client) -> None:
    sandbox = DockerSandbox()
    sandbox.client = mock_docker_client
    mock_container = MagicMock()
    mock_docker_client.containers.run.return_value = mock_container
    with tempfile.TemporaryDirectory() as tmpdir:
        sandbox.base_workspace = tmpdir
        # Setup structure
        os.makedirs(os.path.join(tmpdir, "123/a"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "123/a/b"), exist_ok=True)
        with open(os.path.join(tmpdir, "123/a/f1.txt"), "w") as f:
            f.write("1")
        with open(os.path.join(tmpdir, "123/a/b/f2.txt"), "w") as f:
            f.write("2")
        with open(os.path.join(tmpdir, "123/f3.txt"), "w") as f:
            f.write("3")

        # Test list_dir (non-recursive)
        res = await sandbox.list_dir("/workspace", channel_id=123)
        assert "f3.txt" in res
        assert "a/" in res

        # Test list_dir (recursive)
        res = await sandbox.list_dir("/workspace", channel_id=123, recursive=True)
        res = res.replace("\\", "/")
        assert "a/f1.txt" in res
        assert "a/b/f2.txt" in res

        # Test glob_files
        res = await sandbox.glob_files("*.txt", channel_id=123)
        res = res.replace("\\", "/")
        assert "f3.txt" in res

        res = await sandbox.glob_files("**/*.txt", channel_id=123)
        res = res.replace("\\", "/")
        assert "a/f1.txt" in res
        assert "a/b/f2.txt" in res

        # Test grep_files
        with open(os.path.join(tmpdir, "123/grep.txt"), "w") as f:
            f.write("needle in haystack\nno needle here")
        res = await sandbox.grep_files("needle", channel_id=123)
        res = res.replace("\\", "/")
        assert "grep.txt:1 needle in haystack" in res

        res = await sandbox.grep_files("ghost", channel_id=123)
        assert "No matches for 'ghost'" in res

        # Test find_files
        res = await sandbox.find_files("f*.txt", channel_id=123)
        res = res.replace("\\", "/")
        assert "f3.txt" in res
        assert "a/f1.txt" in res
        assert "a/b/f2.txt" in res

        # Test list_dir error
        res = await sandbox.list_dir("/workspace/ghost", channel_id=123)
        assert "Error: Path not found" in res

        # Test glob_files
        res = await sandbox.glob_files("*.txt", channel_id=123)
        res = res.replace("\\", "/")
        assert "f3.txt" in res

        res = await sandbox.glob_files("**/*.txt", channel_id=123)
        res = res.replace("\\", "/")
        assert "a/f1.txt" in res
        assert "a/b/f2.txt" in res

        # Test grep_files
        with open(os.path.join(tmpdir, "123/grep.txt"), "w") as f:
            f.write("needle in haystack\nno needle here")
        res = await sandbox.grep_files("needle", channel_id=123)
        assert "grep.txt:1 needle in haystack" in res

        res = await sandbox.grep_files("ghost", channel_id=123)
        assert "No matches for 'ghost'" in res

        # Test find_files
        res = await sandbox.find_files("f*.txt", channel_id=123)
        assert "f3.txt" in res
        assert "a/f1.txt" in res
        assert "a/b/f2.txt" in res

@pytest.mark.asyncio
async def test_modal_sandbox_file_ops():
    with patch("modal.App.lookup") as mock_lookup:
        mock_lookup.aio = AsyncMock(return_value=MagicMock())
        with patch("modal.Sandbox.create") as mock_create:
            mock_sandbox = MagicMock()
            mock_create.aio = AsyncMock(return_value=mock_sandbox)
            exec_result = MagicMock()
            exec_result.wait.aio = AsyncMock()
            exec_result.stdout.read.aio = AsyncMock(return_value="success")
            exec_result.stderr = None
            exec_result.returncode = 0
            mock_sandbox.exec.return_value = exec_result
            manager = ModalSandbox()
            assert "success" in await manager.read_file("path", 123)
            assert "File written" in await manager.write_file("path", "content", 123)
            assert "File edited" in await manager.edit_file("path", "old", "new", 123)
            assert "success" in await manager.list_dir("path", 123)
            assert "success" in await manager.glob_files("pattern", 123)
            assert "success" in await manager.grep_files("pattern", 123)
            assert "success" in await manager.find_files("pattern", 123)
            assert "Directory created" in await manager.make_dir("path", 123)

            # Test Modal stop
            mock_sandbox.terminate = MagicMock()
            manager.sandboxes[123] = mock_sandbox
            await manager.stop(123)
            mock_sandbox.terminate.assert_called()
            assert 123 not in manager.sandboxes

            # Test Modal stop all
            manager.sandboxes[456] = mock_sandbox
            await manager.stop()
            assert not manager.sandboxes

@pytest.mark.asyncio
async def test_sandbox_stop_all():
    docker = DockerSandbox()
    docker.client = MagicMock()
    mock_c1 = MagicMock()
    mock_c2 = MagicMock()
    docker.containers[123] = mock_c1
    docker.containers[456] = mock_c2
    await docker.stop()
    mock_c1.stop.assert_called()
    mock_c2.stop.assert_called()
    assert not docker.containers
