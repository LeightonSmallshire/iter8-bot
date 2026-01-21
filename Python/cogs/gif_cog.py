import operator

import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import logging
import os
import random
import utils.bot as bot_utils
import utils.log as log_utils
from typing import Optional

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log', encoding='utf-8'))
_log.addHandler(log_utils.DatabaseHandler())

TENOR_KEY = os.environ["TENOR_TOKEN"]

class GifCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    async def find_best_gif(self, query: str, count: int) -> str | None:
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
        
    # --- Slash Command ---

    @app_commands.command(name='riot', description='RIOT!')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_gif_riot(self, interaction: discord.Interaction):
        url = await self.find_best_gif("rioters", 12)

        embed = discord.Embed(title="RIOT!")
        embed.set_image(url=url)
        embed.set_footer(text="GIFs powered by Tenor", icon_url="https://tenor.com/assets/img/tenor-app-icon.png")  
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name='wok', description='Fuiyooooh!')
    @commands.check(bot_utils.is_guild_paradise)
    async def wok(self, interaction: discord.Interaction):
        url = await self.find_best_gif("wok", 10)

        embed = discord.Embed(title="Fuiyooh!")
        embed.set_image(url=url)
        embed.set_footer(text="GIFs powered by Tenor", icon_url="https://tenor.com/assets/img/tenor-app-icon.png")  
        await interaction.response.send_message(embed=embed)

    # --- Local Command Error Handler (Overrides the global handler for this cog's commands) ---

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """
        Handles errors specifically for commands defined within this cog.
        Note: This specific function is for handling prefix command errors.
        For slash commands, errors are often handled via `on_app_command_error`.
        """
        if isinstance(error, commands.MissingPermissions):
            await interaction.response.send_message(f"You don't have the necessary permissions to run this command.")
        elif isinstance(error, commands.CommandNotFound):
            # This generally won't happen if the command is correctly registered
            pass
        else:
            msg = f'An unhandled command error occurred in cog {self.qualified_name}: {error}'
            _log.error(msg)
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)


# --- Cog Setup Function (MANDATORY for extensions) ---

async def setup(bot: commands.Bot):
    await bot.add_cog(GifCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
