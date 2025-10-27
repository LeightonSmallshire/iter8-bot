import discord
import os, sys, logging
import asyncio, aiohttp
import random, re
import requests
import json
import time
from discord import app_commands
from discord.ext import commands
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import bot_utils

_log = logging.getLogger(__name__)

YT_SEARCH    = "https://www.googleapis.com/youtube/v3/search"
YTDOMAIN     = "https://youtu.be/"

GUILD_ID = int(os.getenv("MAIN_GUILD_ID", "0"))

YTVID_RE = re.compile(r"^[\w-]{11}$")




# --- Helpers ---

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_YT_INITIAL_RE = re.compile(r"ytInitialData\s*=\s*", re.I)

async def fetch_search_html(session: aiohttp.ClientSession, query: str) -> str:
    params = {"search_query": query, "hl": "en"}
    url = "https://www.youtube.com/results"
    timeout = aiohttp.ClientTimeout(total=10)
    async with session.get(url, params=params, headers=HEADERS, timeout=timeout) as resp:
        resp.raise_for_status()
        return await resp.text()

async def fetch_video_data(session: aiohttp.ClientSession, url: str) -> str:
    timeout = aiohttp.ClientTimeout(total=10)
    async with session.get(url, headers=HEADERS, timeout=timeout) as resp:
        resp.raise_for_status()
        return await resp.text()

def extract_yt_initial_data(html: str) -> Dict[str, Any]:
    m = _YT_INITIAL_RE.search(html)
    if not m:
        raise ValueError("ytInitialData not found in HTML")
    start = m.end()
    idx = html.find("{", start)
    if idx == -1:
        raise ValueError("JSON object start not found")

    stack = 0
    esc = False
    in_str = False
    i = idx
    while i < len(html):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                stack += 1
            elif ch == "}":
                stack -= 1
                if stack == 0:
                    json_str = html[idx : i + 1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        raise ValueError("Failed to parse ytInitialData JSON") from e
        i += 1
    raise ValueError("Failed to extract full ytInitialData JSON")

def find_video_renderers(node: Any) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    if isinstance(node, dict):
        vr = node.get("videoRenderer")
        if isinstance(vr, dict):
            found.append(vr)
        else:
            for v in node.values():
                found.extend(find_video_renderers(v))
    elif isinstance(node, list):
        for item in node:
            found.extend(find_video_renderers(item))
    return found

def parse_video_renderer(vr: Dict[str, Any]) -> Dict[str, Optional[str]]:
    vid = vr.get("videoId")
    title = None
    t = vr.get("title") or {}
    runs = t.get("runs") or []
    if runs:
        title = "".join(r.get("text", "") for r in runs)
    else:
        title = t.get("simpleText")

    channel = None
    owner = (vr.get("ownerText") or {}).get("runs") or []
    if owner:
        channel = owner[0].get("text")

    view_count = None
    vc = vr.get("viewCountText") or {}
    if "simpleText" in vc:
        view_count = vc["simpleText"]
    else:
        r = vc.get("runs") or []
        view_count = "".join(x.get("text", "") for x in r) if r else None

    published = None
    pt = vr.get("publishedTimeText") or {}
    if "simpleText" in pt:
        published = pt["simpleText"]

    thumb_url = None
    thumbs = ((vr.get("thumbnail") or {}).get("thumbnails")) or []
    if thumbs:
        thumb_url = thumbs[-1].get("url")

    return {
        "videoId": vid,
        "title": title,
        "url": f"https://www.youtube.com/watch?v={vid}" if vid else None,
        "channel": channel,
        "views": view_count,
        "published": published,
        "thumbnail": thumb_url,
    }

async def search_youtube_scrape(
    session: aiohttp.ClientSession, query: str, max_results: int = 5
):
    html = await fetch_search_html(session, query)
    data = extract_yt_initial_data(html)
    video_renderers = find_video_renderers(data)
    results: List[Dict[str, Optional[str]]] = []
    for vr in video_renderers:
        parsed = parse_video_renderer(vr)
        if parsed["videoId"]:
            results.append((parsed["title"], parsed["videoId"], parsed["channel"]))
            if len(results) >= max_results:
                break
    return results

async def yt_search(session, q, max_results=5):
    return await search_youtube_scrape(session=session, query=q, max_results=max_results)

def trim(s, n=100):
    return s if len(s) <= n else s[: n - 1] + "…"


# --- Actual Cog ---

class YouTubeCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        print(f"Cog '{self.qualified_name}' initialized.")


    @app_commands.command(name="youtube", description="Search YouTube and send a video link")
    @commands.check(bot_utils.is_guild_paradise)
    @app_commands.describe(query="Type to search. Pick a suggestion.")
    async def command_youtube(self, interaction: discord.Interaction, query: str):
        # If user chose an autocomplete option, query == videoId.
        async with aiohttp.ClientSession() as s:
            if YTVID_RE.match(query):
                await interaction.response.send_message(f"{YTDOMAIN}{query}")
                #await youtube_respond(s, interaction=interaction, query=query)
                return

            # Fallback: user typed arbitrary text -> show select menu with top results
            results = await yt_search(s, query, max_results=5)
            
            if not results:
                await interaction.response.send_message("No results.", ephemeral=True)
                return


            vid = results[0]["videoId"]
            await interaction.response.send_message(f"https://youtu.be/{vid}")

    @command_youtube.autocomplete("query")
    @commands.check(bot_utils.is_guild_paradise)
    async def autocomplete_yt_query(self, interaction: discord.Interaction, current: str):
        if not current:
            return []
        try:
            async with aiohttp.ClientSession() as s:
                hits = await yt_search(s, current, max_results=5)
        except Exception:
            return []
        # Autocomplete choices: name shown, value sent to command (use videoId)

        results = [
            app_commands.Choice(name=f"{trim(title or vid, 100 - len(channel) - 3)} - {channel}", value=vid)
            for (title, vid, channel) in hits[:25]
        ]
        return results