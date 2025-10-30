import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import utils.bot as bot_utils
import utils.database as db_utils
import utils.log as log_utils
from typing import Optional
import io
import os
import datetime
import logging
import subprocess
import traceback

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


class DevCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    @app_commands.command(name='logs')
    # @commands.check(bot_utils.is_leighton)
    @app_commands.describe(level="Filter by log level")
    async def get_logs(self, interaction: discord.Interaction, level: Optional[str] = None):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message("No logs 4 U")
        
        rows = await db_utils.read_logs(level=level)
        if not rows:
            await interaction.response.send_message("No logs found.", ephemeral=True)
            return

        formatted = []
        for r in rows:
            formatted.append(f"[{r.timestamp:%Y-%m-%d %H:%M:%S}] [{r.level}] {r.message}")

        msg = "```\n" + "\n".join(formatted) + "\n```"
        if len(msg) > 1950:
            file = discord.file.File(io.StringIO(msg), 'database.log')
            await interaction.response.send_message(file=msg, ephemeral=True)
        else:
            await interaction.response.send_message(content=msg, ephemeral=True)

    @app_commands.command(name='download')
    @commands.check(bot_utils.is_guild_paradise)
    async def do_download(self, interaction: discord.Interaction, path: str):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message("No files 4 U")

        file = discord.File(path)
        await interaction.response.send_message(file=file, ephemeral=True)

    @commands.Cog.listener()
    @commands.check(bot_utils.is_guild_paradise)
    async def on_message(self, message: discord.Message):
        if 'bot broken' in message.content.lower():
            await message.reply('No U')
        if 'boot broekn' in message.content.lower():
            await message.reply('No U booken')

    @app_commands.command(name='crash')
    @commands.check(bot_utils.is_guild_paradise)
    async def do_crash(self, interaction: discord.Interaction):
        if interaction.user.id == bot_utils.Users.Tom:
            await interaction.user.timeout(datetime.timedelta(60), reason='Attemtpting to crash bot')
            return await interaction.response.send_message('Stop it Tom')
        if not bot_utils.is_trusted_developer(interaction):
            await interaction.user.timeout(datetime.timedelta(60), reason='Attemtpting to crash bot')
            return await interaction.response.send_message('No')

        os.abort()
        interaction.response.send_message('past abort somehow')

    @app_commands.command(name='bash')
    @commands.check(bot_utils.is_guild_paradise)
    async def do_bash(self, interaction: discord.Interaction, command: str):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message("No shell 4 U")

        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            process = await asyncio.create_subprocess_shell(
                cmd=command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()
            stdout = stdout.decode().strip()
            stderr = stderr.decode().strip()

            files = []

            if len(stdout) > 0:
                files.append(discord.File(io.StringIO(stdout), 'stdout.txt'))
            if len(stderr) > 0:
                files.append(discord.File(io.StringIO(stderr), 'stderr.txt'))
            await interaction.followup.send(content=f'Command: {command}\nExit code: {process.returncode}', files=files)
        except BaseException as e:
            await interaction.user.send("".join(traceback.format_exc()))

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


async def setup(bot: commands.Bot):
    await bot.add_cog(DevCog(bot))
