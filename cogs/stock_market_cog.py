import operator

import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import logging
import datetime
import asyncio
from utils.model import *
import utils.bot as bot_utils
import utils.database as db_utils
import utils.log as log_utils
from typing import Optional

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


class StockMarketCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")
        self.stock_market_update.start()

    @app_commands.command(name='market', description='Who wants to get rich?')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_market(self, interaction: discord.Interaction):
        """Calculates and displays available stocks."""

        await interaction.response.defer(ephemeral=True, thinking=True)
        embed = discord.Embed(title="📊 The Clockwork Exchange 📊", color=discord.Color.green())

        for stock in await db_utils.get_all_stocks():
            embed.add_field(
                name=f"{stock.code} - {stock.name}",
                value=f"Price - {datetime.timedelta(seconds=round(stock.value))}",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name='buy', description='Buy a stock')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_buy_stock(self, interaction: discord.Interaction, code: str, count: int):
        await interaction.response.defer(ephemeral=True)

        valid, reason = await db_utils.can_afford_stock(interaction.user.id, code, count)
        if not valid:
            await interaction.followup.send(content=reason)
            return

        _, msg = await db_utils.stock_market_buy(interaction.user.id, code, count)
        await interaction.followup.send(content=msg)

    @app_commands.command(name='short', description='Short a stock')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_short_stock(self, interaction: discord.Interaction, code: str, count: int):
        await interaction.response.defer(ephemeral=True)

        valid, reason = await db_utils.can_afford_stock(interaction.user.id, code, count)
        if not valid:
            await interaction.followup.send(content=reason)
            return

        _, msg = await db_utils.stock_market_short(interaction.user.id, code, count)
        await interaction.followup.send(content=msg)

    @app_commands.command(name='close', description='Sell a stock')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_sell_stock(self, interaction: discord.Interaction, trade_id: int):
        await interaction.response.defer(ephemeral=True, thinking=True)

        _, msg = await db_utils.stock_market_sell(interaction.user.id, trade_id)
        await interaction.followup.send(content=msg)

    @app_commands.command(name='portfolio', description='See your portfolio')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_portfolio(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        user_id = interaction.user.id

        orders = await db_utils.get_unsold_orders(user_id)

        if not orders:
            return await interaction.followup.send(
                "You have no open positions.", ephemeral=True
            )

        # ---- Calculate current P&L ----
        total_pl = 0
        lines = []

        for stock, order in orders:
            current_value = stock.value
            pnl_per_unit = (current_value - order.bought_at)

            if order.short:
                pnl_per_unit = -pnl_per_unit

            pnl = pnl_per_unit * order.count
            total_pl += pnl

            lines.append(
                f"**{stock.name} ({stock.code}){' (Short)' if order.short else''}**\n"
                f"- Trade ID: `{order.id}`\n"
                f"- Qty: `{order.count}`\n"
                f"- Bought @ `{datetime.timedelta(seconds=order.bought_at)}`\n"
                f"- Current @ `{datetime.timedelta(seconds=current_value)}`\n"
                f"- P/L: `{'+' if pnl > 0 else '-'}{datetime.timedelta(seconds=abs(pnl))}`\n"
            )

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Portfolio",
            description="\n".join(lines),
            color=discord.Color.green() if total_pl >= 0 else discord.Color.red()
        )

        embed.add_field(
            name="Total P/L",
            value=f"`{'+' if total_pl > 0 else '-'}{datetime.timedelta(seconds=abs(round(total_pl)))}`",
            inline=False
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @tasks.loop(seconds=5)
    async def stock_market_update(self):
        await db_utils.do_stock_market_update(dt=1, sim_count=5)

    @stock_market_update.before_loop
    async def before_update(self):
        await self.bot_.wait_until_ready()

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
    await bot.add_cog(StockMarketCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
