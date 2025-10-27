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

from cogs import bot_utils

_log = logging.getLogger(__name__)


class TimeoutsCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        print(f"Cog '{self.qualified_name}' initialized.")

    # --- Listeners (Events) ---

    @commands.Cog.listener()
    @commands.check(bot_utils.is_guild_paradise)
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Handles member updates, specifically looking for timeout changes."""

        now = datetime.datetime.now(datetime.timezone.utc)

        before_timed_out = (before.timed_out_until is not None) and (before.timed_out_until > now)
        after_timed_out = (after.timed_out_until is not None) and (after.timed_out_until > now)

        timeout_applied = after_timed_out and not before_timed_out

        timeout_extended = (before.timed_out_until is not None) and \
                           (after.timed_out_until is not None) and \
                           (before.timed_out_until < after.timed_out_until)

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
        channel = discord.utils.get(guild.text_channels, name='clockwork-bot')

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
        await bot_utils.send_dm_to_user(1416017385596653649, 'error incoming')

        buf = io.StringIO()
        traceback.print_exc(file=buf)
        message = f'Event: {event}\nArgs: {args}\nkwargs: {kwargs}\nTraceback:\n{buf.read()}'
        # await self.bot_.get_user(1416017385596653649).send(content=message)
        await bot_utils.send_dm_to_user(1416017385596653649, message)

        print(f'Ignoring exception in {event}')
        print("----- ERROR TRACEBACK -----")
        traceback.print_exc(file=sys.stderr)
        print("---------------------------")
        # In a real bot, you might send this traceback to a private log channel.

    @commands.Cog.listener()
    @commands.check(bot_utils.is_guild_paradise)
    async def on_message(self, message: discord.Message):
        if 'bot broken' in message.content:
            await message.reply('No U')

    @app_commands.command(name='bash')
    @commands.check(bot_utils.is_guild_paradise)
    async def do_bash(self, interaction: discord.Interaction, command: str):
        if interaction.user.id != bot_utils.ID_PARADISE_MEMBER_LEIGHTON:
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

            message = f'Command: {command}\n'\
                f'Exit code: {process.returncode}\n'\
                f'{stdout}\n\n'\
                f'{stderr}'

            message = f'{message}  - {len(message)}'

            # if len(message) < 2000 and not command.startswith('cat'):
            #     await interaction.followup.send(content=f'```{message}```'`)
            # else:
            if True:
                files = []
                
                if len(stdout) > 0:
                    files.append( discord.File(io.StringIO(stdout), 'stdout.txt'))
                if len(stderr) > 0:
                    files.append( discord.File(io.StringIO(stderr), 'stderr.txt'))
                await interaction.followup.send(content=f'Command: {command}\nExit code: {process.returncode}', files=files)

            # await interaction.user.send(content=message)
            # await interaction.response.send_message(message, ephemeral=True)
            # await interaction.followup.send(message, ephemeral=True)
        except BaseException as e:
            buf = io.StringIO()
            traceback.print_exc(file=buf)
            message = f'Event: {e}\nTraceback:\n{buf.read()}'
            await interaction.user.send(message)

            user = self.bot_.get_user(1416017385596653649)
            await interaction.user.send(repr(user))

    # --- Slash Command ---

    # @app_commands.command(
    #     name="show_leaderboard",
    #     description="Displays the current server XP/level leaderboard."
    # )
    @app_commands.command(name='leaderboard', description='Show timeout leaderboards')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_show_leaderboard(self, interaction: discord.Interaction):
        """Generates and displays the timeout leaderboard from audit logs."""
        leaderboard = {}

        async for entry in interaction.guild.audit_logs(limit=None, action=discord.AuditLogAction.member_update):
            member = entry.target

            was_timeout = getattr(entry.changes.before, 'timed_out_until', None)
            now_timeout = getattr(entry.changes.after, 'timed_out_until', None)
            was_timeout = was_timeout or datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)
            now_timeout = now_timeout or datetime.datetime(1, 1, 1, tzinfo=datetime.timezone.utc)

            b_was_timeout = (was_timeout >= entry.created_at)
            b_now_timeout = (now_timeout >= entry.created_at)

            timeout_added = not b_was_timeout and b_now_timeout
            timeout_changed = b_was_timeout and b_now_timeout
            timeout_removed = b_was_timeout and not b_now_timeout

            if timeout_added:
                duration = now_timeout - entry.created_at
                # print('added', duration)
                total_timeouts, total_duration = leaderboard.get(member.display_name, [0, datetime.timedelta()])
                leaderboard[member.display_name] = (total_timeouts + 1, total_duration + duration)

            if timeout_changed:
                duration = now_timeout - was_timeout
                # print('changed', duration)
                total_timeouts, total_duration = leaderboard.get(member.display_name, [0, datetime.timedelta()])
                leaderboard[member.display_name] = (total_timeouts, total_duration + duration)

            if timeout_removed:
                duration = was_timeout - entry.created_at
                # print('removed', duration)
                total_timeouts, total_duration = leaderboard.get(member.display_name, [0, datetime.timedelta()])
                leaderboard[member.display_name] = (total_timeouts, total_duration - duration)

        sorted_leaderboard = sorted(
            leaderboard.items(),
            key=operator.itemgetter(1),
            reverse=True
        )

        embed = discord.Embed(
            title='👑 Timeout Leaderboard 👑',
            color=discord.Color.red()
        )

        for rank, (user, (total_timeouts, total_duration)) in enumerate(sorted_leaderboard, start=1):
            total_duration: datetime.timedelta
            total_duration -= datetime.timedelta(microseconds=total_duration.microseconds)

            value = (f"**{total_timeouts}** Timeout{'s' if total_timeouts != 1 else ''}"
                     + f' {total_duration}')

            if rank == 1:
                field_name = f"🥇 {user}"
            elif rank == 2:
                field_name = f"🥈 {user}"
            elif rank == 3:
                field_name = f"🥉 {user}"
            else:
                field_name = f"#{rank}: {user}"

            embed.add_field(name=field_name, value=value, inline=False)

        # Send the final response
        await interaction.response.send_message(embed=embed, ephemeral=False)

    # --- Local Command Error Handler (Overrides the global handler for this cog's commands) ---

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """
        Handles errors specifically for commands defined within this cog.
        Note: This specific function is for handling prefix command errors.
        For slash commands, errors are often handled via `on_app_command_error`.
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
    # await bot_utils.send_dm_to_user(1416017385596653649, 'error incoming')
    
    await bot.add_cog(TimeoutsCog(bot))

# Optional: You can also include an 'async def teardown(bot: commands.Bot):' function
# to clean up resources when the cog is unloaded.
# async def teardown(bot: commands.Bot):
#     print(f"Cog '{ModerationCog.qualified_name}' unloaded.")
