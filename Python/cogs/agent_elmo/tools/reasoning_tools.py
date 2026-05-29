from langchain_core.tools import tool


@tool
async def respond(content: str) -> str:
    """Call this with your final response when you are ready to answer the user."""
    return content
