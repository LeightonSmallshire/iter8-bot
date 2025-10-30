import asyncio
import operator

import discord
from discord.ext import commands
from discord import app_commands
import traceback
import logging
import sys
import datetime
import subprocess
import os
import io

import cogs.utils.bot as bot_utils
import cogs.utils.database as db_utils
import cogs.utils.log as log_utils

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


class TimeoutsCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Listeners (Events) ---

    @commands.Cog.listener()
    @commands.check(bot_utils.is_guild_paradise)
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Handles member updates, specifically looking for timeout changes."""

        now = datetime.datetime.now(datetime.timezone.utc)

        before_timed_out = (before.timed_out_until is not None) and (before.timed_out_until > now)
        after_timed_out = (after.timed_out_until is not None) and (after.timed_out_until > now)

        timeout_applied = after_timed_out and not before_timed_out

        timeout_removed = before_timed_out and not after_timed_out

        timeout_extended = (before.timed_out_until is not None) and \
                           (after.timed_out_until is not None) and \
                           (before.timed_out_until < after.timed_out_until)

        duration_to_add = datetime.timedelta(seconds=0)
        if timeout_applied:
            duration_to_add = after.timed_out_until - now
        elif timeout_removed:
            duration_to_add = now - before.timed_out_until
        elif timeout_extended:
            duration_to_add = after.timed_out_until - before.timed_out_until

        # await db_utils.update_timeout_leaderboard(after.id, duration_to_add.total_seconds())

        if timeout_applied or timeout_extended:
            _log.info(f'Timeout in {after.guild.name} : {after.name} : until {after.timed_out_until}')

            moderator = None
            reason = None

            async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
                if entry.target and entry.target.id == after.id and entry.changes.after and hasattr(entry.changes.after,
                                                                                                    'timed_out_until'):
                    moderator = entry.user
                    reason = entry.reason if entry.reason else "Fun!"
                    break
            else:
                _log.debug("Moderator/Reason not found in recent audit logs.")

            await self.on_member_timeout(after, after.timed_out_until, moderator, reason)

    @staticmethod
    async def on_member_timeout(member: discord.Member,
                                until: datetime.datetime,
                                moderator: discord.Member | None,
                                reason: str | None):
        """Handles the event after a member is timed out."""
        guild = member.guild
        # Using client.get_channel for potential better performance/caching if ID is known,
        # but discord.utils.get by name is fine too.
        channel = discord.utils.get(guild.text_channels, id=bot_utils.Channels.ParadiseClockwork)

        if channel is None:
            _log.critical(f"Couldn't find channel 'clockwork-bot' to post in")
            return

        if (moderator is None) or (reason is None):
            # Fallback message
            await channel.send(f'{member.mention} was timed out <t:{int(until.timestamp())}:R>',
                               silent=True)

        else:
            # Full message with moderator and reason
            await channel.send(
                f'{member.mention} was timed out by {moderator.mention} for **{reason}** <t:{int(until.timestamp())}:R>',
                silent=True)

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """
        Listener for unhandled errors that occur during event processing.
        This provides a catch-all for logic errors not caught by a command error handler.
        """
        bot_utils.defer_message(self.bot_, bot_utils.Users.Leighton, 'error incoming')

        buf = io.StringIO()
        traceback.print_exc(file=buf)
        message = f'Event: {event}\nArgs: {args}\nkwargs: {kwargs}\nTraceback:\n{buf.read()}'
        # await self.bot_.get_user(bot_utils.Users.Leighton).send(content=message)
        bot_utils.defer_message(self.bot_, bot_utils.Users.Leighton, message)

        print(f'Ignoring exception in {event}')
        print("----- ERROR TRACEBACK -----")
        traceback.print_exc(file=sys.stderr)
        print("---------------------------")
        # In a real bot, you might send this traceback to a private log channel.

    # --- Slash Command ---

    # @app_commands.command(
    #     name="show_leaderboard",
    #     description="Displays the current server XP/level leaderboard."
    # )
    @app_commands.command(name='leaderboard', description='Show timeout leaderboards')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_show_leaderboard(self, interaction: discord.Interaction):
        """Generates and displays the timeout leaderboard from audit logs."""

        # Getting leaderboard might take time
        await interaction.response.defer(thinking=True)

        leaderboard = await bot_utils.get_timeout_data(interaction.guild)
        # leaderboard = await db_utils.get_timeout_leaderboard()

        embed = discord.Embed(
            title='👑 Timeout Leaderboard 👑',
            color=discord.Color.red()
        )

        for rank, timeout in enumerate(leaderboard, start=1):
            value = (f"**{timeout.count}** Timeout{'s' if timeout.count != 1 else ''}"
                     + f' {datetime.timedelta(seconds=round(timeout.duration))}')

            user = await interaction.guild.fetch_member(timeout.id)

            if rank == 1:
                field_name = f"🥇 {user.display_name}"
            elif rank == 2:
                field_name = f"🥈 {user.display_name}"
            elif rank == 3:
                field_name = f"🥉 {user.display_name}"
            else:
                field_name = f"#{rank}: {user.display_name}"

            embed.add_field(name=field_name, value=value, inline=False)

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
    await bot.add_cog(TimeoutsCog(bot))
