import operator

import discord
from discord.ext import commands
from discord import app_commands
from wcwidth import wcswidth
import traceback
import logging
import re
import datetime
import utils.bot as bot_utils
import utils.log as log_utils
import utils.database as db_utils
from typing import Optional
from collections import Counter, defaultdict

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


class GamblingCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---
    @app_commands.command(name='bookies', description='iter8 does not condone gambling. BUT HAVE FUN!')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_bookies(self, interaction: discord.Interaction):
        """Generates and displays the gambling info."""

        def disp_width(s: str) -> int:
            return wcswidth(s)
        
        await interaction.response.defer(thinking=True)

        users = bot_utils.get_non_bot_users(interaction)
        users += await db_utils.get_extra_admin_rolls(consume=False)

        counts = Counter(users)

        embed = discord.Embed(title="🎰 Welcome to the Bookies 🎰", color=discord.Color.blue())

        member_by_id = {m.id: m for m in interaction.guild.members}

        async def get_member(user_id: int) -> discord.Member:
            return member_by_id.get(user_id) or await interaction.guild.fetch_member(user_id)

        # Compute max display width for alignment
        max_name_w = 0
        for uid in counts:
            name = await get_member(uid)
            max_name_w = max(max_name_w, disp_width(name.display_name))

        for (user_id, count) in counts.items():
            user = await get_member(user_id)
            bets = await db_utils.get_bets(user_id)

            strings = [f"{(await get_member(bet_user)).display_name} has bet {datetime.timedelta(seconds=round(amount))}" for (bet_user, amount) in bets.items()]

            pad = max_name_w - disp_width(user.display_name)
            embed.add_field(
                name=f"`{user.display_name}{' ' * pad} - {count}/{len(users)}`",
                value="\n".join(strings) or "\u200b",
                inline=False,
            )

        embed.set_footer(text=f"Place your bets with /bet <user> <duration>")

        await interaction.followup.send(embed=embed)
    
    class DurationTransformer(app_commands.Transformer):
        _DURATION_RE = re.compile(r"(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?$", re.I)

        def parse_duration(self, s: str) -> datetime.timedelta:
            m = self._DURATION_RE.fullmatch(s.strip())
            if not m:
                raise ValueError("Use formats like 1h30m, 45m, 90s, 2h, 1d2h.")
            d, h, m_, s_ = (int(x) if x else 0 for x in m.groups())
            td = datetime.timedelta(days=d, hours=h, minutes=m_, seconds=s_)
            if td.total_seconds() <= 0:
                raise ValueError("Duration must be > 0.")
            return td
        
        async def transform(self, interaction: discord.Interaction, value: str) -> datetime.timedelta:
            try:
                return self.parse_duration(value)
            except ValueError as e:
                # Surface a friendly error in the UI
                await interaction.response.send_message(content=str(e), ephemeral=True)
                raise app_commands.AppCommandError(str(e))
    
    @app_commands.command(name='bet', description='iter8 does not condone gambling. BUT HAVE FUN!')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_bet(self, interaction: discord.Interaction, user: discord.Member, duration: app_commands.Transform[datetime.timedelta, DurationTransformer]):
        """Bet on someone to be the next admin!"""
        
        await interaction.response.defer(thinking=True)

        if (user.bot or interaction.guild.owner_id == user.id):
            await interaction.followup.send(f"❌ You can't bet on bots.")
            return

        if not await db_utils.can_afford_purchase(interaction.user.id, round(duration.total_seconds())):
            await interaction.followup.send(f"❌ You can't afford to bet for that duration.")
            return
        
        await db_utils.record_gamble(interaction.user.id, user.id, round(duration.total_seconds()))
        await interaction.followup.send(f"✅ <@{interaction.user.id}> have placed a bet of {duration} on <@{user.id}> to be the next admin!")

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
    await bot.add_cog(GamblingCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
