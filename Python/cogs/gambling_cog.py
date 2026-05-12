
import datetime
import re
from collections import Counter

import discord
import logfire
from discord import app_commands
from discord.ext import commands
from wcwidth import wcswidth

import utils.bot as bot_utils
import utils.gamble as gamble_utils
import utils.shop as shop_utils

_log = logfire


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

        guild = interaction.guild
        assert guild is not None
        users = bot_utils.get_non_bot_users(interaction)

        counts = Counter(users)

        embed = discord.Embed(title="🎰 Welcome to the Bookies 🎰", color=discord.Color.blue())

        member_by_id = {m.id: m for m in guild.members}

        async def get_member(user_id: int) -> discord.Member | None:
            return member_by_id.get(user_id) or await guild.fetch_member(user_id)

        # Compute max display width for alignment
        max_name_w = 0
        for uid in counts:
            name = await get_member(uid)
            max_name_w = max(max_name_w, disp_width(name.display_name if name else "???"))

        odds = await gamble_utils.get_gamble_odds(consume_bets=False)
        prize = sum([data["total"] for (_, data)  in odds.items()])

        def fmt_duration(seconds: float) -> str:
            return str(datetime.timedelta(seconds=round(seconds)))

        embed.add_field(
            name=f"Total to Win:\t\t\t\t\t\t\t{datetime.timedelta(seconds=prize)}",
            value="\n",
            inline=False,
        )

        # white space
        embed.add_field(
            name="\n",
            value="\n",
            inline=False,
        )

        for target_id, target_info in odds.items():
            user = await get_member(target_id)
            total = target_info["total"]
            target_odds = target_info["odds"]

            user_name = user.display_name if user else "???"
            line = (
                f"{user_name:<{max_name_w}}"
                f"  {fmt_duration(total):>8}"
                f"  {target_odds * 100:6.2f}%"
            )

            bettor_lines = []
            for bettor_id, bet_info in target_info["bettors"].items():
                bettor = await get_member(bettor_id)
                bettor_name = bettor.display_name if bettor else "???"
                bettor_lines.append(
                    f"{bettor_name:<{max_name_w}}"
                    f"  {fmt_duration(bet_info['amount']):>8}"
                    f"  {bet_info['odds'] * 100:6.2f}%"
                )

            block = f"\n```{line}```\n"
            subblock = "```\n" + "\n".join(bettor_lines) + "\n```"

            embed.add_field(
                name=block,
                value=subblock,
                inline=False,
            )

        embed.set_footer(text="Place your bets with /bet <user> <duration>")

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
                raise app_commands.AppCommandError(str(e)) from e

    @app_commands.command(name='bet', description='iter8 does not condone gambling. BUT HAVE FUN!')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_bet(self, interaction: discord.Interaction, user: discord.Member, duration: app_commands.Transform[datetime.timedelta, DurationTransformer]):
        """Bet on someone to be the next admin!"""

        await interaction.response.defer(thinking=True)

        assert interaction.guild is not None
        if (user.bot or interaction.guild.owner_id == user.id):
            await interaction.followup.send("❌ You can't bet on bots.")
            return

        if not await shop_utils.can_afford_purchase(interaction.user.id, round(duration.total_seconds())):
            await interaction.followup.send("❌ You can't afford to bet for that duration.")
            return

        await gamble_utils.record_gamble(interaction.user.id, user.id, round(duration.total_seconds()))
        await interaction.followup.send(f"✅ <@{interaction.user.id}> have placed a bet of {duration} on <@{user.id}> to be the next admin!")

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

async def setup(bot: commands.Bot):
    await bot.add_cog(GamblingCog(bot))
