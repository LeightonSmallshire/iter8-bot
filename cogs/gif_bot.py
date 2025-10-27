import operator

import discord
from discord.ext import commands
from discord import app_commands
import traceback
import aiohttp
import logging
import os
import sys
import random
import datetime
from typing import Optional

from cogs import bot_utils

_log = logging.getLogger(__name__)

TENOR_KEY = os.getenv("TENOR_KEY")       

async def find_best_gif(query: str, count: int) -> str | None:
    url = "https://tenor.googleapis.com/v2/search"
    params = {
        "q": query,
        "key": TENOR_KEY,
        "media_filter": "gif,mediumgif",  # keep payload small
        "limit": count,
    }
    async with aiohttp.ClientSession() as s:
        async with s.get(url, params=params) as r:
            data = await r.json()

    results = data.get("results", [])
    if not results:
        return None

    # Heuristic: prefer "gif", then "mediumgif", then "tinygif"
    def pick_url(item):
        mf = item.get("media_formats", {})
        for key in ("gif", "mediumgif", "tinygif"):
            if key in mf and "url" in mf[key]:
                return mf[key]["url"]
        return None

    # Filter to items that actually have a gif-like URL
    candidates = [pick_url(x) for x in results]
    candidates = [c for c in candidates if c]
    if not candidates:
        return None
    return random.choice(candidates)

class GifCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        print(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---

    @app_commands.command(name='riot', description='RIOT!')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_bot_broken(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        url = await find_best_gif("rioters", 12)

        embed = discord.Embed(title="RIOT!")
        embed.set_image(url=url)
        embed.set_footer(text="GIFs powered by Tenor", icon_url="https://tenor.com/assets/img/tenor-app-icon.png")  
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='wok', description='Fuiyooh')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_bot_working(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        url = await find_best_gif("wok", 10)

        embed = discord.Embed(title="Fuiyooh!")
        embed.set_image(url=url)
        embed.set_footer(text="GIFs powered by Tenor", icon_url="https://tenor.com/assets/img/tenor-app-icon.png")  
        await interaction.response.send_message(embed=embed)


    # --- Local Command Error Handler (Overrides the global handler for this cog's commands) ---

    async def on_app_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """
        Handles errors specifically for commands defined within this cog.
        """
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"You don't have the necessary permissions to run this command.")
        elif isinstance(error, commands.CommandNotFound):
            # This generally won't happen if the command is correctly registered
            pass
        else:
            print(f'An unhandled command error occurred in cog {self.qualified_name}: {error}')



# --- Cog Setup Function (MANDATORY for extensions) ---

async def setup(bot: commands.Bot):
    await bot.add_cog(GifCog(bot))

# Optional: You can also include an 'async def teardown(bot: commands.Bot):' function
# to clean up resources when the cog is unloaded.
# async def teardown(bot: commands.Bot):
#     print(f"Cog '{ModerationCog.qualified_name}' unloaded.")
