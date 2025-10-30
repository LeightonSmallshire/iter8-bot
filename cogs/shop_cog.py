import operator

import discord
from discord.ext import commands
from discord import app_commands
import traceback
import logging
import sys
import datetime
import cogs.utils.bot as bot_utils
import cogs.utils.log as log_utils
import cogs.utils.database as db_utils
from typing import Optional

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('logs.log'))
_log.addHandler(log_utils.DatabaseHandler())

class ShopCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---

    @app_commands.command(name='shop', description='Let\'s see what the lovely shop has to offer')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_shop(self, interaction: discord.Interaction):
        """Generates and displays the timeout shop."""

        # Getting leaderboard might take time
        await interaction.response.defer(thinking=True)

        shop = await db_utils.get_shop_contents()

        embed = discord.Embed(
            title='Timeout Shop 🛒',
            color=discord.Color.blue()
        )

        for item in shop:
            embed.add_field(name=item.description, value=f"Price: {datetime.timedelta(seconds=item.cost)}", inline=False)
            
        # Send the final response
        await interaction.followup.send(embed=embed, ephemeral=False)


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
            _log.error(f'An unhandled command error occurred in cog {self.qualified_name}: {error}')


# --- Cog Setup Function (MANDATORY for extensions) ---

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
