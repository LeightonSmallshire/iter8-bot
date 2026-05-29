import aiohttp
import trafilatura
from ddgs import DDGS
from langchain_core.tools import tool


@tool
async def web_search(query: str) -> str:
    """Search the web using DuckDuckGo."""
    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=3):
            results.append(f"Title: {r['title']}\nSnippet: {r['body']}\nURL: {r['href']}")
    return "\n\n".join(results) if results else "No results found."


@tool
async def read_url(url: str) -> str:
    """Fetch and read the text content of a URL (no JavaScript)."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Iter8Bot/1.0)"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session, session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
            html = await response.text()
    except aiohttp.ClientError as e:
        return f"Error fetching URL: {str(e)}"

    try:
        text = trafilatura.extract(html, output_format="markdown", include_comments=False, no_fallback=False)
        if not text:
            return "Could not extract meaningful content from this page."
        return text[:10000] + ("..." if len(text) > 10000 else "")
    except Exception as e:
        return f"Error extracting content: {str(e)}"
