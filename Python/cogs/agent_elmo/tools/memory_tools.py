from typing import Any

from langchain_core.tools import tool


@tool
async def remember(content: str, mem0_client: Any, channel_id: int) -> str:
    """Explicitly save information to memory using mem0."""
    if not mem0_client:
        return "Error: mem0 not configured."
    try:
        mem0_client.add(content, user_id=str(channel_id))
        return f"Remembered: {content}"
    except Exception as e:
        return f"Error saving to memory: {str(e)}"

@tool
async def recall(query: str, mem0_client: Any, channel_id: int) -> str:
    """Search memories using mem0 semantic search."""
    if not mem0_client:
        return "Error: mem0 not configured."
    try:
        results = mem0_client.search(query, filters={"user_id": str(channel_id)})
        if not results:
            return f"No memories found for: {query}"
        return "Memories:\n" + "\n".join([f"- {r}" for r in results])
    except Exception as e:
        return f"Error searching memories: {str(e)}"
