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
from typing import Optional

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


class BotBrokenCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---

    @app_commands.command(name='broken', description='Bot is broken')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_bot_broken(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        user_target = user.id if user is not None else bot_utils.Users.Leighton

        _log.info(f"Broken command from {interaction.user.display_name}")

        message = f"<@{user_target}> bot broken"
        channel = interaction.client.get_channel(bot_utils.Channels.ParadiseBotBrokenSpam)
        await interaction.response.defer(ephemeral=True, thinking=True)
        await channel.send(message)
        await interaction.delete_original_response()

    @app_commands.command(name='working', description='Bot is working')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_bot_working(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        user_target = user.id if user is not None else bot_utils.Users.Leighton

        _log.info(f"Broken command from {interaction.user.display_name}")

        message = f"<@{user_target}> bot working"
        channel = interaction.client.get_channel(bot_utils.Channels.ParadiseBotBrokenSpam)
        await interaction.response.defer(ephemeral=True, thinking=True)
        await channel.send(message)
        await interaction.delete_original_response()

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
    await bot.add_cog(BotBrokenCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
