
import asyncio
import datetime
import io
import sys
import traceback
from typing import Any

import discord
import logfire
from discord import app_commands
from discord.ext import commands

import utils.bot as bot_utils
import utils.timeout as timeout_utils

_log = logfire

_AUDIT_TIMEOUT_ACTIONS: tuple[discord.AuditLogAction, ...] = (
    discord.AuditLogAction.automod_timeout_member,
    discord.AuditLogAction.automod_quarantine_user,
    discord.AuditLogAction.member_update,
)
_AUDIT_WINDOW = datetime.timedelta(minutes=2)
_AUDIT_ATTEMPTS = 3
_AUDIT_RETRY_DELAY = 1.5


def _actor_label(actor: discord.User | discord.Member | None, is_automod: bool) -> str | None:
    if is_automod:
        return "AutoMod"
    if actor is not None:
        return actor.mention
    return None


class TimeoutsCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Listeners (Events) ---

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Handles member updates, specifically looking for timeout changes."""
        if after.guild.id != bot_utils.Guilds.Default:
            return

        now = datetime.datetime.now(datetime.UTC)

        before_timed_out = (before.timed_out_until is not None) and (before.timed_out_until > now)
        after_timed_out = (after.timed_out_until is not None) and (after.timed_out_until > now)

        timeout_applied = after_timed_out and not before_timed_out

        timeout_removed = before_timed_out and not after_timed_out

        timeout_extended = (before.timed_out_until is not None) and \
                           (after.timed_out_until is not None) and \
                           (before.timed_out_until < after.timed_out_until)

        duration_to_add = datetime.timedelta(seconds=0)
        if timeout_applied and after.timed_out_until is not None:
            duration_to_add = after.timed_out_until - now
        elif timeout_removed and before.timed_out_until is not None:
            duration_to_add = now - before.timed_out_until
        elif timeout_extended and after.timed_out_until is not None and before.timed_out_until is not None:
            duration_to_add = after.timed_out_until - before.timed_out_until

        has_changed = timeout_applied or timeout_extended or timeout_removed

        if has_changed:
            _log.info(f'Timeout in {after.guild.name} : {after.name} : until {after.timed_out_until}')

            found, actor, reason, is_automod = await self._find_timeout_actor(after)
            if not found:
                _log.debug("Moderator/Reason not found in recent audit logs.")

            # Do not count timeouts by server owner (but do count removals)
            actor_is_owner = actor is not None and actor.id == after.guild.owner_id
            if found and (not actor_is_owner or timeout_removed):
                await timeout_utils.update_timeout_leaderboard(after.id, duration_to_add.total_seconds())

            if timeout_applied or timeout_extended:
                if after.timed_out_until is not None:
                    await self.on_member_timeout(after, after.timed_out_until, actor, reason, is_automod)
            else:
                await self.on_member_untimeout(after, actor, is_automod)

    @staticmethod
    async def _find_timeout_actor(
        member: discord.Member,
    ) -> tuple[bool, discord.User | discord.Member | None, str | None, bool]:
        cutoff = datetime.datetime.now(datetime.UTC) - _AUDIT_WINDOW
        for attempt in range(_AUDIT_ATTEMPTS):
            best: discord.AuditLogEntry | None = None
            best_is_automod = False
            for action in _AUDIT_TIMEOUT_ACTIONS:
                try:
                    async for entry in member.guild.audit_logs(limit=50, action=action):
                        if entry.created_at < cutoff:
                            break
                        if entry._target_id != member.id:
                            continue
                        if action is discord.AuditLogAction.member_update and not hasattr(
                            entry.changes.after, "timed_out_until"
                        ):
                            continue
                        if best is None or entry.created_at > best.created_at:
                            best = entry
                            best_is_automod = action is not discord.AuditLogAction.member_update
                except discord.Forbidden:
                    _log.warning("audit_log_access_denied")
                    return False, None, None, False
                except discord.HTTPException as e:
                    _log.warning("audit_log_fetch_failed", error=str(e))
            if best is not None:
                reason = best.reason or ("Fun!" if not best_is_automod else None)
                return True, best.user, reason, best_is_automod
            if attempt + 1 < _AUDIT_ATTEMPTS:
                await asyncio.sleep(_AUDIT_RETRY_DELAY)
        return False, None, None, False

    @staticmethod
    async def on_member_timeout(member: discord.Member,
                                 until: datetime.datetime,
                                 actor: discord.User | discord.Member | None,
                                 reason: str | None,
                                 is_automod: bool) -> None:
        """Handles the event after a member is timed out."""
        guild = member.guild
        # Using client.get_channel for potential better performance/caching if ID is known,
        # but discord.utils.get by name is fine too.
        channel = discord.utils.get(guild.text_channels, id=bot_utils.Channels.ParadiseClockwork)

        if channel is None:
            _log.error("Couldn't find channel 'clockwork-bot' to post in")
            return

        label = _actor_label(actor, is_automod)
        stamp = f'<t:{int(until.timestamp())}:R>'
        if label is None:
            content = f'{member.mention} was timed out {stamp}'
        elif reason is None:
            content = f'{member.mention} was timed out by {label} {stamp}'
        else:
            content = f'{member.mention} was timed out by {label} for **{reason}** {stamp}'

        await channel.send(content, silent=True)

    @staticmethod
    async def on_member_untimeout(member: discord.Member,
                                  actor: discord.User | discord.Member | None,
                                  is_automod: bool) -> None:
        """Handles the event after a member is released from a time out."""
        guild = member.guild
        # Using client.get_channel for potential better performance/caching if ID is known,
        # but discord.utils.get by name is fine too.
        channel = discord.utils.get(guild.text_channels, id=bot_utils.Channels.ParadiseClockwork)

        if channel is None:
            _log.error("Couldn't find channel 'clockwork-bot' to post in")
            return

        label = _actor_label(actor, is_automod)
        if label is None:
            content = f'{member.mention} was freed from their time out.'
        else:
            content = f'{member.mention} was freed from their time out by {label}.'

        await channel.send(content, silent=True)

    @commands.Cog.listener()
    async def on_error(self, event: Any, *args: Any, **kwargs: Any) -> None:
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

    @app_commands.command(name='leaderboard', description='Show timeout leaderboards')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_show_leaderboard(self, interaction: discord.Interaction) -> None:
        """Generates and displays the timeout leaderboard from audit logs."""

        # Getting leaderboard might take time
        await interaction.response.defer(thinking=True)

        leaderboard = await timeout_utils.get_timeout_leaderboard()

        embed = discord.Embed(
            title='👑 Timeout Leaderboard 👑',
            color=discord.Color.red()
        )

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("Guild not found.", ephemeral=True)
            return

        for rank, timeout in enumerate(leaderboard, start=1):
            value = (f"**{timeout.count}** Timeout{'s' if timeout.count != 1 else ''}"
                     + f' {datetime.timedelta(seconds=round(timeout.duration))}')

            try:
                user = await guild.fetch_member(timeout.id)
            except Exception:
                await timeout_utils.erase_timeout_user(timeout.id)

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
            await interaction.response.send_message("You don't have the necessary permissions to run this command.")
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TimeoutsCog(bot))
