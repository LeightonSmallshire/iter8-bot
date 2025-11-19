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
import utils.stock as stock_utils
from typing import Optional

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


class StockMarketCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    @app_commands.command(name='market', description='Who wants to get rich?')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_market(self, interaction: discord.Interaction):
        """Calculates and displays available stocks."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        await db_utils.update_market_since_last_action()

        embed = discord.Embed(title="📊 The Clockwork Exchange 📊", color=discord.Color.green())

        for stock in await db_utils.get_all_stocks():
            low, high = stock_utils.calculate_buy_sell_price(stock)
            embed.add_field(
                name=f"{stock.code} - {stock.name}",
                value=f"Buy - {datetime.timedelta(seconds=round(high))}\nSell - {datetime.timedelta(seconds=round(low))}",
                inline=False,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name='buy', description='Buy a stock')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_buy_stock(self, interaction: discord.Interaction, code: str, count: int):
        await interaction.response.defer(ephemeral=True)

        await db_utils.update_market_since_last_action()
        
        valid, reason = await db_utils.can_afford_stock(interaction.user.id, code, count)
        if not valid:
            await interaction.followup.send(content=reason)
            return

        _, msg = await db_utils.stock_market_buy(interaction.user.id, code, count)
        await interaction.followup.send(content=msg, ephemeral=False)

    @app_commands.command(name='short', description='Short a stock')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_short_stock(self, interaction: discord.Interaction, code: str, count: int):
        await interaction.response.defer(ephemeral=True)

        await db_utils.update_market_since_last_action()

        valid, reason = await db_utils.can_afford_stock(interaction.user.id, code, count)
        if not valid:
            await interaction.followup.send(content=reason)
            return

        _, msg = await db_utils.stock_market_short(interaction.user.id, code, count)
        await interaction.followup.send(content=msg, ephemeral=False)


    class IntListTransformer(app_commands.Transformer):
        async def transform(self, interaction: discord.Interaction, value: str) -> list[int]:
            parts = [p for p in value.replace(",", " ").split() if p]
            return [int(p) for p in parts]
    

    @app_commands.command(
        name='close', 
        description='Close one or more of your trades. Price may change for later trades from closing earlier trades.'
    )
    @commands.check(bot_utils.is_guild_paradise)
    async def command_sell_stock(self, interaction: discord.Interaction, trade_ids: app_commands.Transform[list[int], IntListTransformer]):
        await interaction.response.defer(ephemeral=True, thinking=True)

        await db_utils.update_market_since_last_action()

        for trade_id in trade_ids:
            _, msg = await db_utils.stock_market_sell(interaction.user.id, trade_id)
            await interaction.followup.send(content=msg, ephemeral=False)

    @app_commands.command(name='portfolio', description='See your portfolio')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_portfolio(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        await db_utils.update_market_since_last_action()

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
            sell_price, _ = stock_utils.calculate_buy_sell_price(stock)

            current_value = sell_price
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
