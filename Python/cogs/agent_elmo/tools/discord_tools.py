import os
import random
from typing import Any

import aiohttp
import discord
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict

TENOR_KEY = os.environ.get("TENOR_TOKEN", "")


class SendGifInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    query: str

@tool(args_schema=SendGifInput, infer_schema=False)
async def send_gif(query: str, bot: Any, channel_id: int) -> str:
    """Send a GIF to the channel using Tenor."""
    if not TENOR_KEY:
        return "Error: Tenor API key not configured."
    try:
        url = "https://tenor.googleapis.com/v2/search"
        params = {"query": query, "key": TENOR_KEY, "media_filter": "gif,mediumgif", "limit": "10"}
        async with aiohttp.ClientSession() as s, s.get(url, params=params) as r:
            data = await r.json()
        results = data.get("results", [])
        if not results:
            return "No GIF found."

        item = random.choice(results)
        gif_url = item.get("media_formats", {}).get("gif", {}).get("url") or item.get("media_formats", {}).get("mediumgif", {}).get("url")
        if not gif_url:
            return "Error: Could not extract GIF URL."

        channel = bot.get_channel(channel_id)
        if not channel:
            return "Error: Could not find channel."
        embed = discord.Embed()
        embed.set_image(url=gif_url)
        embed.set_footer(text="GIFs powered by Tenor")
        await channel.send(embed=embed)
        return f"Sent GIF for: {query}"
    except Exception as e:
        return f"Error sending GIF: {str(e)}"

class TimeoutUserInput(BaseModel):
    model_config = ConfigDict(extra="allow")
    user_id: int
    reason: str
    duration_seconds: int

@tool(args_schema=TimeoutUserInput, infer_schema=False)
async def timeout_user(user_id: int, reason: str, duration_seconds: int, bot: Any, channel_id: int) -> str:
    """Timeout (mute) a user in the guild. duration_seconds max 300."""
    duration_seconds = min(duration_seconds, 300)
    try:
        channel = bot.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return "Error: Invalid channel."
        guild = channel.guild
        member = guild.get_member(user_id)
        if not member:
            return "Error: User not found in guild."

        from datetime import UTC, datetime, timedelta
        until = datetime.now(UTC) + timedelta(seconds=duration_seconds)
        await member.timeout(until, reason=f"[bot] {reason}")
        return f"User {member.name} timed out for {duration_seconds} seconds."
    except Exception as e:
        return f"Error timing out user: {str(e)}"
