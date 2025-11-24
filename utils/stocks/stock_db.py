from ..model import Stock
from ..database import *
from typing import Callable, Awaitable


#-----------------------------------------------------------------
#   Stock Market

async def get_all_stocks() -> list[Stock]:
    async with Database(DATABASE_NAME) as db:
        return await db.select(Stock)
    
async def get_unsold_orders(user_id: int) -> list[tuple[Stock, Trade]]:
    async with Database(DATABASE_NAME) as db:
        return await db.join_select(Stock, Trade, where=[WhereParam("r.user_id", user_id), WhereParam("r.sold_at", None, "IS")])
    
async def can_afford_stock(user_id: int, stock_id: str, count: int) -> tuple[bool, Optional[str]]:
    credit = await get_shop_credit(user_id)

    async with Database(DATABASE_NAME) as db:
        stocks = await db.select(Stock, where=[WhereParam("code", stock_id.upper())])
        if not stocks:
            return False, "Trying to buy a stock that doesn't exist!"
        
        stock = stocks[0]

        _, buy_price = calculate_buy_sell_price(stock)
        
        if (buy_price * count) < credit:
            return True, None
        else:
            return False, "Can't afford this purchase!"

async def do_stock_market_update(db, dt: float, autosell_callback: Callable[[str], Awaitable]):
    stocks = await db.select(Stock)
    time_frames = dt / 5.0  # 15 minute intervals
    dt = await update_stocks_rand(stocks,time_frames) * 5.0

    for stock in stocks:
        await db.update(stock)

        low, high = calculate_buy_sell_price(stock)
        autosell_trades = await db.select(Trade, where=[WhereParam("stock", stock.id), WhereParam("sold_at", None), [WhereParam("auto_sell_low", None, "IS NOT"), WhereParam("auto_sell_high", None, "IS NOT")]])
        for trade in autosell_trades:
            sell = (trade.auto_sell_low is not None and trade.auto_sell_low > low) or (trade.auto_sell_high is not None and trade.auto_sell_high < high)
            if sell:
                success, msg = await close_market_trade(db, trade.user_id, trade.id)
                if (success):
                    await autosell_callback(msg)
    return dt

async def do_stock_market_directions_update(db, iterations : int):
    if(iterations>0):
        stocks = await db.select(Stock)
        for stock in stocks:
            for i in range( math.ceil(iterations) ):
                await update_stock_direction(stock)
            await db.update(stock)

        
async def update_market_since_last_action(autosell_callback: Callable[[str], Awaitable]):
    async with Database(DATABASE_NAME) as db:
        timestamps = await db.select(Timestamps)

        five_min_diff = math.floor( datetime.datetime.now().minute / 15 ) - math.floor( timestamps.last_market_update.minute / 15 )
        await do_stock_market_directions_update(db,five_min_diff)

        dt = (datetime.datetime.now() - timestamps.last_market_update).total_seconds()
        dt = await do_stock_market_update(db, dt, autosell_callback)

        timestamps.last_market_update = datetime.datetime.now() - datetime.timedelta(seconds=dt)
        await db.update(timestamps)

async def stock_market_buy(user_id: int, stock_id: str, count: int, auto_sell_low: Optional[datetime.timedelta], auto_sell_high: Optional[datetime.timedelta]) -> tuple[bool, str]:
    async with Database(DATABASE_NAME) as db:
        stocks = await db.select(Stock, where=[WhereParam("code", stock_id.upper())])
        if not stocks:
            return False, "Trying to buy a stock that doesn't exist!"
        
        stock = stocks[0]

        _, buy_price = calculate_buy_sell_price(stock)

        sell_low = auto_sell_low.total_seconds() if auto_sell_low else None
        sell_high = auto_sell_high.total_seconds() if auto_sell_high else None

        buy = Trade(None, count, buy_price, None, user_id, stock.id, short=False, auto_sell_low=sell_low, auto_sell_high=sell_high)
        msg =  f"<@{user_id}> bought {count} shares of {stock.code} @ {buy_price}s"

        await order_stock(db, stock, count)
        await db.insert(buy)

        return True, msg

async def stock_market_short(user_id: int, stock_id: str, count: int, auto_sell_low: Optional[datetime.timedelta], auto_sell_high: Optional[datetime.timedelta]) -> tuple[bool, str]:
    async with Database(DATABASE_NAME) as db:
        stocks = await db.select(Stock, where=[WhereParam("code", stock_id.upper())])
        if not stocks:
            return False, "Trying to short a stock that doesn't exist!"
        
        stock = stocks[0]

        buy_price, _ = calculate_buy_sell_price(stock)

        sell_low = auto_sell_low.total_seconds() if auto_sell_low else None
        sell_high = auto_sell_high.total_seconds() if auto_sell_high else None

        short = Trade(None, count, buy_price, None, user_id, stock.id, short=True, auto_sell_low=sell_low, auto_sell_high=sell_high)
        msg =  f"<@{user_id}> shorted {count} shares of {stock.code} @ {buy_price}s"

        await order_stock(db, stock, -count)
        await db.insert(short)
            
        return True, msg
    
async def close_market_trade(db, user_id: int, trade_id: int) -> tuple[bool, str]:
    orders = await db.select(Trade, where=[WhereParam("id", trade_id), WhereParam("user_id", user_id), WhereParam("sold_at", None, "IS")])
    if not orders:
        return False, "Trying to close a trade that doesn't exist."
    
    order = orders[0]

    stocks = await db.select(Stock, where=[WhereParam("id", order.stock)])
    if not stocks:
        return False, "Trying to close a trade for a stock that doesn't exist."
    
    stock = stocks[0]
    pl = 0.0

    sell_price, sell_price_short = calculate_buy_sell_price(stock)

    order.sold_at = sell_price_short if order.short else sell_price
    pl += order.sold_at - order.bought_at
    pl *= order.count

    await db.update(order)
    await order_stock(db, stock, order.count if order.short else -order.count)

    if order.short:
        pl *= -1

    return True, f"<@{user_id}> sold {order.count} shares of {stock.code} for a profit/loss of {'+' if pl > 0 else '-'}{datetime.timedelta(seconds=abs(round(pl)))}"

async def stock_market_sell(user_id: int, trade_id: int) -> tuple[bool, str]:
    async with Database(DATABASE_NAME) as db:
        return await close_market_trade(db, user_id, trade_id)
