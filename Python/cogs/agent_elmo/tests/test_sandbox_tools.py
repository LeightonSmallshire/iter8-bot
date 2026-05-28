from unittest.mock import AsyncMock, MagicMock

import pytest

from cogs.agent_elmo.sandbox.manager import Sandbox
from cogs.agent_elmo.tools import sandbox_tools


@pytest.mark.asyncio
async def test_bash_error():
    mock_sandbox = MagicMock(spec=Sandbox)
    mock_sandbox.exec_command = AsyncMock(return_value=MagicMock(exit_code=1, output="Error occurred"))

    result = await sandbox_tools.bash.ainvoke({"command": "fail", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Exit code: 1" in result

@pytest.mark.asyncio
async def test_file_ops_errors():
    mock_sandbox = MagicMock(spec=Sandbox)
    mock_sandbox.read_file = AsyncMock(return_value="Error reading")
    mock_sandbox.write_file = AsyncMock(return_value="Error writing")
    mock_sandbox.edit_file = AsyncMock(return_value="Error editing")
    mock_sandbox.list_dir = AsyncMock(return_value="Error listing")
    mock_sandbox.glob_files = AsyncMock(return_value="Error globbing")
    mock_sandbox.grep_files = AsyncMock(return_value="Error grepping")
    mock_sandbox.find_files = AsyncMock(return_value="Error finding")
    mock_sandbox.make_dir = AsyncMock(return_value="Error mkdir")
    mock_sandbox.delete_file = AsyncMock(return_value="Error deleting")

    assert "Error reading" in await sandbox_tools.read_file.ainvoke({"path": "path", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Error writing" in await sandbox_tools.write_file.ainvoke({"path": "path", "content": "c", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Error editing" in await sandbox_tools.edit_file.ainvoke({"path": "path", "old_text": "o", "new_text": "n", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Error listing" in await sandbox_tools.list_dir.ainvoke({"path": "path", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Error globbing" in await sandbox_tools.glob_files.ainvoke({"pattern": "p", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Error grepping" in await sandbox_tools.grep_files.ainvoke({"pattern": "p", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Error finding" in await sandbox_tools.find_files.ainvoke({"name_pattern": "p", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Error mkdir" in await sandbox_tools.make_dir.ainvoke({"path": "path", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Error deleting" in await sandbox_tools.delete_file.ainvoke({"path": "path", "sandbox": mock_sandbox, "channel_id": 123})

@pytest.mark.asyncio
async def test_run_python_error():
    # Test type checking error
    result = await sandbox_tools.run_python.ainvoke({"code": "x: int = 'not int'"})
    assert "Type checking failed" in result

    # Test execution error
    result = await sandbox_tools.run_python.ainvoke({"code": "raise Exception('Boom')"})
    assert "Execution Failed" in result
