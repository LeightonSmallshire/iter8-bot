import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cogs.agent_elmo.tools import memory_tools

@pytest.mark.asyncio
async def test_remember_success():
    mock_client = MagicMock()
    mock_client.add = MagicMock(return_value="Success")
    result = await memory_tools.remember.ainvoke({"content": "Test memory", "mem0_client": mock_client, "channel_id": 123})
    assert "Remembered" in result
    mock_client.add.assert_called_once_with("Test memory", user_id="123")

@pytest.mark.asyncio
async def test_remember_no_client():
    result = await memory_tools.remember.ainvoke({"content": "Test memory", "mem0_client": None, "channel_id": 123})
    assert "Error: mem0 not configured" in result

@pytest.mark.asyncio
async def test_remember_error():
    mock_client = MagicMock()
    mock_client.add.side_effect = Exception("API Error")
    result = await memory_tools.remember.ainvoke({"content": "Test memory", "mem0_client": mock_client, "channel_id": 123})
    assert "Error saving to memory" in result

@pytest.mark.asyncio
async def test_recall_success():
    mock_client = MagicMock()
    mock_client.search.return_value = ["Memory 1", "Memory 2"]
    result = await memory_tools.recall.ainvoke({"query": "test query", "mem0_client": mock_client, "channel_id": 123})
    assert "Memories:" in result
    assert "Memory 1" in result
    mock_client.search.assert_called_once_with("test query", filters={"user_id": "123"})

@pytest.mark.asyncio
async def test_recall_no_results():
    mock_client = MagicMock()
    mock_client.search.return_value = []
    result = await memory_tools.recall.ainvoke({"query": "test query", "mem0_client": mock_client, "channel_id": 123})
    assert "No memories found" in result

@pytest.mark.asyncio
async def test_recall_no_client():
    result = await memory_tools.recall.ainvoke({"query": "test query", "mem0_client": None, "channel_id": 123})
    assert "Error: mem0 not configured" in result

@pytest.mark.asyncio
async def test_recall_error():
    mock_client = MagicMock()
    mock_client.search.side_effect = Exception("API Error")
    result = await memory_tools.recall.ainvoke({"query": "test query", "mem0_client": mock_client, "channel_id": 123})
    assert "Error searching memories" in result
