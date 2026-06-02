from unittest.mock import AsyncMock

import pytest

from cogs.agent_elmo.util import easy_send, split_message_for_discord


def test_split_message_short():
    msg = "Hello world"
    assert split_message_for_discord(msg) == ["Hello world"]

def test_split_message_long():
    msg = "a" * 2000
    chunks = split_message_for_discord(msg)
    assert len(chunks) > 1
    assert len(chunks[0]) <= 1900

def test_split_message_code_block():
    msg = "Start\n```python\n" + "x = 1\n" * 500 + "\n```\nEnd"
    chunks = split_message_for_discord(msg)
    assert len(chunks) > 1
    assert chunks[0] == "Start\n"
    assert chunks[1].startswith("```python")

def test_split_message_mixed():
    msg = "Text " + "a" * 1800 + " ```code``` " + "b" * 200
    chunks = split_message_for_discord(msg)
    assert len(chunks) > 1

def test_split_message_spoilers():
    msg = "Hidden ||spoiler|| and " + "a" * 1900 + " more ||spoiler||"
    chunks = split_message_for_discord(msg)
    assert len(chunks) > 1
    assert any("||spoiler||" in c for c in chunks)

def test_split_message_empty():
    assert split_message_for_discord("") == []

@pytest.mark.asyncio
async def test_easy_send():
    mock_channel = AsyncMock()
    await easy_send(mock_channel, "Hello" * 1000)
    assert mock_channel.send.called
