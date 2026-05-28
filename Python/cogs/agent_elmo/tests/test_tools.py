from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cogs.agent_elmo.sandbox.manager import Sandbox
from cogs.agent_elmo.tools import discord_tools, sandbox_tools, web_tools


@pytest.mark.asyncio
async def test_web_search() -> None:
    with patch("ddgs.DDGS.text") as mock_text:
        mock_text.return_value = [{"title": "Test", "body": "Snippet", "href": "url"}]
        result = await web_tools.web_search.ainvoke({"query": "test query"})
        assert "Test" in result
        assert "Snippet" in result

@pytest.mark.asyncio
async def test_sandbox_bash() -> None:
    mock_sandbox = MagicMock(spec=Sandbox)
    mock_sandbox.exec_command = AsyncMock(return_value=MagicMock(exit_code=0, output="Success"))

    result = await sandbox_tools.bash.ainvoke({"command": "ls", "sandbox": mock_sandbox, "channel_id": 123})
    assert "Success" in result

@pytest.mark.asyncio
async def test_run_python() -> None:
    result = await sandbox_tools.run_python.ainvoke({"code": "print('hello')"})
    assert "hello" in result

@pytest.mark.asyncio
async def test_discord_send_gif() -> None:
    mock_bot = MagicMock()
    mock_channel = AsyncMock()
    mock_bot.get_channel.return_value = mock_channel

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={"results": [{"media_formats": {"gif": {"url": "url"}}}]})
        mock_get.return_value.__aenter__.return_value = mock_response

        # Mock environment
        with patch("cogs.agent_elmo.tools.discord_tools.TENOR_KEY", "key"):
            result = await discord_tools.send_gif.ainvoke({"query": "cat", "bot": mock_bot, "channel_id": 123})
            assert "Sent GIF" in result
            mock_channel.send.assert_called()

