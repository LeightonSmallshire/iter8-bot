"""Tests for agent_elmo tools."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext

from cogs.agent_elmo.deps import BaseDeps
from cogs.agent_elmo.docker_manager import DockerManager
from cogs.agent_elmo.tools import task


@pytest.fixture
def mock_ctx():
    """Create a mock RunContext with BaseDeps."""
    docker_manager = MagicMock(spec=DockerManager)
    deps = BaseDeps(docker_manager=docker_manager, channel_id=123456)
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


@pytest.mark.asyncio
async def test_task_tool_creates_agent(mock_ctx):
    """Test that task tool creates an agent with given system prompt."""
    with patch("pydantic_ai.Agent") as mock_agent_class:
        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=MagicMock(output="Test output"))
        mock_agent_class.return_value = mock_agent
        result = await task(mock_ctx, "You are a test agent.", "Test message")
        assert "Task Agent Result" in result
        assert "Test output" in result
        # Verify Agent was called with system_prompt (last call is from task tool)
        last_call = mock_agent_class.call_args_list[-1]
        assert last_call.kwargs.get("system_prompt") == "You are a test agent."


@pytest.mark.asyncio
async def test_task_tool_with_docker_hint(mock_ctx):
    """Test that task tool registers Docker tools when hinted in system prompt."""
    with patch("pydantic_ai.Agent") as mock_agent_class:
        mock_agent = MagicMock()
        mock_agent.tool = MagicMock()
        mock_agent.run = AsyncMock(return_value=MagicMock(output="Code written"))
        mock_agent_class.return_value = mock_agent
        result = await task(mock_ctx, "You are a coding agent. Use Docker tools.", "Write code")
        assert "Task Agent Result" in result
        # Check that docker tools were registered (tool() called at least once)
        assert mock_agent.tool.called
