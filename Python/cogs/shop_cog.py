import operator

import discord
from discord.ext import commands
from discord import app_commands
from itertools import groupby
import logging
import datetime
import utils.bot as bot_utils
import utils.log as log_utils
import utils.shop as shop_utils
from view.shop_view import ShopView
import utils.misc

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log', encoding='utf-8'))
_log.addHandler(log_utils.DatabaseHandler())


class ShopCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---

    @app_commands.command(name='shop', description='Let\'s see what the lovely shop has to offer')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_shop(self, interaction: discord.Interaction) -> None:
        """Generates and displays the timeout shop."""

        await interaction.response.defer(ephemeral=True, thinking=True)

        sale, end_date = await shop_utils.is_ongoing_sale()
        discount = 0.5 if sale else 1
        embed = discord.Embed(title="Timeout Shop 🛒", color=discord.Color.blue())

        groups = [(cat, list(g)) for cat, g in groupby(shop_utils.SHOP_ITEMS, key=lambda x: x.CATEGORY)]
        for (idx, (category, group)) in enumerate(groups, 1):
            embed.add_field(name=f"{category}", value="────────────────────────────────────────────────────────", inline=False)

            for item in group:
                cost = item.COST * discount if item.ITEM_ID != shop_utils.BlackFridaySaleItem.ITEM_ID else item.COST 

                embed.add_field(
                    name=item.DESCRIPTION,
                    value=f"Price: {datetime.timedelta(seconds=cost)}",
                    inline=False,
                )

            if (idx != len(groups)):
                embed.add_field(name="", value="\u200b", inline=False)

        if sale:
            embed.set_footer(text=f"Sale ends at {end_date}")

        view = ShopView()
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name='credit', description='Find out how much shop credit everyone has')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_credit(self, interaction: discord.Interaction) -> None:
        """Calculates and displays available shop credit."""

        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = interaction.guild
        if guild is None:
            return

        users_list: list[tuple[discord.Member, float]] = [(user, await shop_utils.get_shop_credit(user.id)) for user in guild.members if not user.bot and user.id != guild.owner_id]
        users_list = sorted(users_list, key=operator.itemgetter(1), reverse=True)

        embed = discord.Embed(title="💵 How much is everyone worth? 💵", color=discord.Color.blue())
        for (user, credit) in users_list:
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
