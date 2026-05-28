from langchain_core.tools import tool
from ddgs import DDGS

@tool
async def web_search(query: str) -> str:
    """Search the web using DuckDuckGo."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=3):
            results.append(f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}")
    return "\n\n".join(results) if results else "No results found."
