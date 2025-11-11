import operator

import discord
from discord.ext import commands
from discord import app_commands
import traceback
import logging
import sys
import datetime
import utils.bot as bot_utils
import utils.log as log_utils
import utils.database as db_utils
import utils.shop as shop_utils
from view.shop_view import ShopView
from typing import Optional

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
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

        await interaction.response.defer(thinking=True)

        embed = discord.Embed(title="Timeout Shop 🛒", color=discord.Color.blue())
        for item in shop_utils.SHOP_ITEMS:
            embed.add_field(
                name=item.DESCRIPTION,
                value=f"Price: {datetime.timedelta(seconds=item.COST)}",
                inline=False,
            )

        view = ShopView()
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name='credit', description='Find out how much shop credit everyone has')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_credit(self, interaction: discord.Interaction):
        """Calculates and displays available shop credit."""

        await interaction.response.defer(thinking=True)

        users = { user: await db_utils.get_shop_credit(user.id) for user in interaction.guild.members if not user.bot and not user.id == interaction.guild.owner_id }
        users = sorted(users.items(), key=operator.itemgetter(1), reverse=True)

        embed = discord.Embed(title="How much is everyone worth? 💵", color=discord.Color.blue())
        for (user, credit) in users:
            embed.add_field(
                name=user.display_name,
                value=f"{datetime.timedelta(seconds=round(credit.total_seconds()))}",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

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
