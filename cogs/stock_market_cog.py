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
import utils.stocks.stock_control_params as stock_utils
from typing import Optional

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())

def get_format_price(total: float) -> str:
    sign = "-" if total < 0 else ""
    total = abs(total)
    # seconds with 2 digits before decimal, 4 after: SS.FFFF
    return f"{sign}{total:06.4f}s"

async def print_stock_market_trade(guild: discord.Guild, msg: str):
    channel = guild.get_channel(bot_utils.Channels.StockMarketSpam) or await guild.fetch_channel(bot_utils.Channels.StockMarketSpam)
    await channel.send(content=msg, silent=True)

class StockMarketCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")
        self.market_display_loop.start()
    
    class DurationTransformer(app_commands.Transformer):
        _DURATION_RE = re.compile(
            r"""
            ^\s*
            (?:(?P<days>\d+)\s*d)?\s*              # 1d
            (?:(?P<hours>\d+)\s*h)?\s*             # 2h
            (?:(?P<minutes>\d+)\s*m(?!s))?\s*      # 3m  (but NOT ms)
            (?:(?P<seconds>\d+)\s*s)?\s*           # 4s
            (?:(?P<milliseconds>\d+)\s*ms)?\s*     # 500ms
            $
            """,
            re.I | re.X,
        )

        def parse_duration(self, s: str) -> datetime.timedelta:
            m = self._DURATION_RE.fullmatch(s.strip())
            if not m:
                raise ValueError("Use formats like 1h30m, 45m, 90s, 2h, 1d2h.")
            d, h, m_, s_, ms_ = (int(x) if x else 0 for x in m.groups())
            td = datetime.timedelta(days=d, hours=h, minutes=m_, seconds=s_, milliseconds=ms_)
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

    async def build_market_summary_embed(self) -> discord.Embed:
        embed = discord.Embed(title="📊 The Clockwork Exchange 📊", color=discord.Color.green())

        for stock in await db_utils.get_all_stocks():
            low, high = stock_utils.calculate_buy_sell_price(stock)
            embed.add_field(
                name=f"{stock.code} - {stock.name}",
                value=f"Buy - {get_format_price(high)}\nSell - {get_format_price(low)}",
                inline=False,
            )
        return embed

    async def update_market(self) -> discord.Embed:
        guild = self.bot_.get_guild(bot_utils.Guilds.Paradise) or await self.bot_.fetch_guild(bot_utils.Guilds.Paradise)
        channel = guild.get_channel(bot_utils.Channels.StockMarketSummary) or await guild.fetch_channel(bot_utils.Channels.StockMarketSummary)
        
        await db_utils.update_market_since_last_action(lambda x: print_stock_market_trade(guild, x))
        
        embed = await self.build_market_summary_embed()

        embed.set_footer(text=f"Last updated: {datetime.datetime.now().replace(microsecond=0)}")

        edited = False
        async for msg in channel.history(limit=1):
            await msg.edit(embed=embed)
            edited = True

        if not edited:
            await channel.send(embed=embed)

        return embed

    @app_commands.command(name='market', description='Who wants to get rich?')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_market(self, interaction: discord.Interaction):
        """Calculates and displays available stocks."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        embed = await self.update_market()

        await interaction.followup.send(embed=embed)

    @app_commands.command(name='buy', description='Buy a stock')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_buy_stock(self, 
        interaction: discord.Interaction, 
        code: str, 
        count: int, 
        autosell_low: Optional[app_commands.Transform[datetime.timedelta, DurationTransformer]],
        autosell_high: Optional[app_commands.Transform[datetime.timedelta, DurationTransformer]]
    ):
        await interaction.response.defer(ephemeral=True)

        await self.update_market()
        
        valid, reason = await db_utils.can_afford_stock(interaction.user.id, code, count)
        if not valid:
            await interaction.followup.send(content=reason)
            return

        success, msg = await db_utils.stock_market_buy(interaction.user.id, code, count, autosell_low, autosell_high)
        
        if success:
            await print_stock_market_trade(interaction.guild, msg)
            await interaction.followup.send(content="✅ Transaction complete")
        else:
            await interaction.followup.send(content=f"❌ Transaction failed [{msg}]")

    @app_commands.command(name='short', description='Short a stock')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_short_stock(self, 
        interaction: discord.Interaction, 
        code: str, 
        count: int, 
        autosell_low: Optional[app_commands.Transform[datetime.timedelta, DurationTransformer]],
        autosell_high: Optional[app_commands.Transform[datetime.timedelta, DurationTransformer]]
    ):
        await interaction.response.defer(ephemeral=True)

        await self.update_market()

        valid, reason = await db_utils.can_afford_stock(interaction.user.id, code, count)
        if not valid:
            await interaction.followup.send(content=reason)
            return

        success, msg = await db_utils.stock_market_short(interaction.user.id, code, count, autosell_low, autosell_high)
        
        if success:
            await print_stock_market_trade(interaction.guild, msg)
            await interaction.followup.send(content="✅ Transaction complete")
        else:
            await interaction.followup.send(content=f"❌ Transaction failed [{msg}]")


    class IntListTransformer(app_commands.Transformer):
        async def transform(self, interaction: discord.Interaction, value: str) -> list[int]:
            try:
                parts = [p for p in value.replace(",", " ").split() if p]
                return [int(p) for p in parts]
            except ValueError as e:
                # Surface a friendly error in the UI
                await interaction.response.send_message(content=str(e), ephemeral=True)
                raise app_commands.AppCommandError(str(e))
    

    @app_commands.command(
        name='close', 
        description='Close one or more of your trades. Price may change for later trades from closing earlier trades.'
    )
    @commands.check(bot_utils.is_guild_paradise)
    async def command_sell_stock(self, interaction: discord.Interaction, trade_ids: app_commands.Transform[list[int], IntListTransformer]):
        await interaction.response.defer(ephemeral=True, thinking=True)

        await self.update_market()

        for trade_id in trade_ids:
            success, msg = await db_utils.stock_market_sell(interaction.user.id, trade_id)
        
            if success:
                await print_stock_market_trade(interaction.guild, msg)
                await interaction.followup.send(content="✅ Transaction complete", ephemeral=True)
            else:
                await interaction.followup.send(content=f"❌ Transaction failed [{msg}]", ephemeral=True)

    @app_commands.command(name='portfolio', description='See your portfolio')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_display_portfolio(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        await self.update_market()

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
            sell_price, sell_price_short = stock_utils.calculate_buy_sell_price(stock)

            current_value = sell_price_short if order.short else sell_price
            pnl_per_unit = (current_value - order.bought_at)

            if order.short:
                pnl_per_unit = -pnl_per_unit

            pnl = pnl_per_unit * order.count
            total_pl += pnl

            lines.append(
                f"**{stock.name} ({stock.code}){' (Short)' if order.short else''}**\n"
                f"- Trade ID: `{order.id}`\n"
                f"- Qty: `{order.count}`\n"
                f"- Bought @ `{get_format_price(order.bought_at)}`\n"
                f"- Current @ `{get_format_price(current_value)}`\n"
                f"- P/L: `{'+' if pnl > 0 else '-'}{datetime.timedelta(seconds=abs(pnl))}`\n"
            )

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Portfolio",
            description="\n".join(lines),
            color=discord.Color.green() if total_pl >= 0 else discord.Color.red()
        )

        embed.add_field(
            name="Total P/L",
            value=f"`{'+' if total_pl > 0 else '-'}{datetime.timedelta(seconds=abs(total_pl))}`",
            inline=False
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


    @tasks.loop(minutes=15)
    async def market_display_loop(self):
        await self.update_market()

    @market_display_loop.before_loop
    async def before_my_task(self):
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
            msg = f'An unhandled command error occurred in cog {self.qualified_name}: {error}'
            _log.error(msg)
            await interaction.response.send_message(msg, ephemeral=True)
        
# --- Cog Setup Function (MANDATORY for extensions) ---

async def setup(bot: commands.Bot):
    await bot.add_cog(StockMarketCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
