import datetime
import operator

import discord
import logfire
from discord import app_commands
from discord.ext import commands

import utils.bot as bot_utils
import utils.misc
import utils.shop as shop_utils

_log = logfire


class ShopCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---

    @app_commands.command(name='credit', description='Find out how much shop credit everyone has')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_credit(self, interaction: discord.Interaction) -> None:
        """Calculates and displays available shop credit."""

        await interaction.response.defer(ephemeral=True, thinking=True)

        assert interaction.guild is not None
        user_credits: dict[discord.Member, float] = {user: await shop_utils.get_shop_credit(user.id) for user in interaction.guild.members if not user.bot and user.id != interaction.guild.owner_id}
        sorted_users: list[tuple[discord.Member, float]] = sorted(user_credits.items(), key=operator.itemgetter(1), reverse=True)

        embed = discord.Embed(title="💵 How much is everyone worth? 💵", color=discord.Color.blue())
        for user, credit in sorted_users:
            embed.add_field(
                name=user.display_name,
                value=utils.misc.format_timedelta(datetime.timedelta(seconds=round(credit))),
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
    await bot.add_cog(ShopCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
