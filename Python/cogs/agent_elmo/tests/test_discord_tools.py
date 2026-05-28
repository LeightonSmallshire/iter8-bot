from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from cogs.agent_elmo.tools import discord_tools


@pytest.mark.asyncio
async def test_send_gif():
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

@pytest.mark.asyncio
async def test_timeout_user_success():
    mock_bot = MagicMock()
    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.guild = MagicMock()
    mock_member = MagicMock()
    mock_member.timeout = AsyncMock()
    mock_channel.guild.get_member.return_value = mock_member
    mock_bot.get_channel.return_value = mock_channel

    result = await discord_tools.timeout_user.ainvoke({"user_id": 123, "reason": "being mean", "duration_seconds": 60, "bot": mock_bot, "channel_id": 456})
    assert "timed out" in result
    mock_member.timeout.assert_called_once()

@pytest.mark.asyncio
async def test_timeout_user_not_found():
    mock_bot = MagicMock()
    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.guild = MagicMock()
    mock_channel.guild.get_member.return_value = None
    mock_bot.get_channel.return_value = mock_channel

    result = await discord_tools.timeout_user.ainvoke({"user_id": 123, "reason": "being mean", "duration_seconds": 60, "bot": mock_bot, "channel_id": 456})
    assert "Error: User not found in guild" in result

@pytest.mark.asyncio
async def test_timeout_user_forbidden():
    mock_bot = MagicMock()
    mock_channel = MagicMock(spec=discord.TextChannel)
    mock_channel.guild = MagicMock()
    mock_member = MagicMock()
    mock_member.timeout.side_effect = Exception("Forbidden")
    mock_channel.guild.get_member.return_value = mock_member
    mock_bot.get_channel.return_value = mock_channel

    result = await discord_tools.timeout_user.ainvoke({"user_id": 123, "reason": "being mean", "duration_seconds": 60, "bot": mock_bot, "channel_id": 456})
    assert "Error timing out user" in result
