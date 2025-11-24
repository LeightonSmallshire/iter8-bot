from .model import Stock
from .database import *
from typing import Callable, Awaitable
import math

STOCK_BASE_PRICE                = 1
STOCK_BASE_DRIFT                = 0
STOCK_BASE_VOLATILITY           = 0.005
STOCK_BASE_VOLUME               = 100

STOCK_PRICE_IMPACT              = 0.00001
STOCK_DRIFT_IMPACT              = 0.000001
STOCK_VOLATILITY_IMPACT         = 0.00002

STOCK_HIGH_VOLUME               = 100 * STOCK_BASE_VOLUME

STOCK_DECAY_FACTOR              = 0.995
STOCK_VOLUME_ALPHA              = 0.05
STOCK_SPREAD_VOLATILITY_FACTOR  = 1
STOCK_SPREAD_VOLUME_FACTOR      = 1

STOCK_BASE_PRICE_SPREAD         = 0.001 # 0.1%

STOCK_ACTOR_SIM_COUNT           = 1
STOCK_ACTOR_SIM_BUY_RANGE       = 100

class Stocks:
    JackpotGeniusDeluxe         = Stock(None, "JackpotGeniusDeluxe",    "JGD", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME)
    BingoCommunity              = Stock(None, "BingoCommunity",         "BCM", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME)
    StarWheel                   = Stock(None, "StarWheel",              "STW", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME)
    SavannahFrenzy              = Stock(None, "SavannahFrenzy",         "SVF", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME)
    CheekyMonkeyCommunity       = Stock(None, "CheekyMonkeyCommunity",  "CMC", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME)
    WildDevils                  = Stock(None, "WildDevilsCommunity",    "WDC", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME)
    Crusher                     = Stock(None, "Crusher",                "CSH", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME)

AVAILABLE_STOCKS: list[Stock] = [
    Stocks.JackpotGeniusDeluxe,
    Stocks.BingoCommunity,
    Stocks.StarWheel,
    Stocks.SavannahFrenzy,
    Stocks.CheekyMonkeyCommunity,
    Stocks.WildDevils,
    Stocks.Crusher,
]

def calculate_buy_sell_price(stock: Stock) -> tuple[float, float]:
    # low liquidity widens spreads (inverse of volume)
    vol_term = STOCK_SPREAD_VOLATILITY_FACTOR * stock.volatility  
    liq_term = 2 / (stock.volume ** STOCK_SPREAD_VOLUME_FACTOR)

    spread = min(0.10, STOCK_BASE_PRICE_SPREAD + vol_term + liq_term)

    low = stock.value * (1 - spread)
    high = stock.value * (1 + spread)

    return low, high




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
        
async def do_stock_update(db, stock: Stock, count: int):
    # EMA smoothing
    stock.volume = (1 - STOCK_VOLUME_ALPHA) * stock.volume + STOCK_VOLUME_ALPHA * abs(count)

    liquidity = math.sqrt(max(stock.volume, 1))
    effective_impact = (STOCK_PRICE_IMPACT * count) / liquidity

    stock.value *= (1 + effective_impact)
    stock.drift += STOCK_DRIFT_IMPACT * count / liquidity
    stock.volatility += abs(count) * STOCK_VOLATILITY_IMPACT / liquidity
    stock.volatility = max(0.0001, min(stock.volatility, 1.0))
    await db.update(stock)

async def do_stock_market_update(db, dt: float, sim_count: int, autosell_callback: Callable[[str], Awaitable]):
    stocks = await db.select(Stock)
    for _ in range(sim_count):
        trade_count = random.randint(-STOCK_ACTOR_SIM_BUY_RANGE, STOCK_ACTOR_SIM_BUY_RANGE)
        await do_stock_update(db, random.choice(stocks), trade_count)

    for stock in stocks:
        mu = stock.drift
        sigma = stock.volatility
        z = random.gauss(0, 1)

        stock.value *= math.exp((mu - 0.5 * sigma * sigma) * dt +
                                sigma * math.sqrt(dt) * z)
        
        quiet_factor = max(STOCK_DECAY_FACTOR, 1 - stock.volume / STOCK_HIGH_VOLUME)

        stock.drift *= quiet_factor
        stock.volatility = STOCK_BASE_VOLATILITY + (stock.volatility - STOCK_BASE_VOLATILITY) * quiet_factor

        # clamp vol to avoid collapse or explosion
        stock.volatility = max(0.001, min(stock.volatility, 1.0))

        await db.update(stock)

        low, high = calculate_buy_sell_price(stock)
        autosell_trades = await db.select(Trade, where=[WhereParam("stock", stock.id), WhereParam("sold_at", None), [WhereParam("auto_sell_low", None, "IS NOT"), WhereParam("auto_sell_high", None, "IS NOT")]])
        for trade in autosell_trades:
            sell = (trade.auto_sell_low is not None and trade.auto_sell_low > low) or (trade.auto_sell_high is not None and trade.auto_sell_high < high)
            if sell:
                success, msg = await close_market_trade(db, trade.user_id, trade.id)
                if (success):
                    await autosell_callback(msg)

        
async def update_market_since_last_action(autosell_callback: Callable[[str], Awaitable]):
    async with Database(DATABASE_NAME) as db:
        timestamps = await db.select(Timestamps)

        dt = (datetime.datetime.now() - timestamps.last_market_update).total_seconds()
        while dt >= 5:
            await do_stock_market_update(db, 1, STOCK_ACTOR_SIM_COUNT, autosell_callback)
            dt -= 5

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

        await do_stock_update(db, stock, count)
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

        await do_stock_update(db, stock, -count)
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
    await do_stock_update(db, stock, order.count if order.short else -order.count)

    if order.short:
        pl *= -1

    return True, f"<@{user_id}> sold {order.count} shares of {stock.code} for a profit/loss of {'+' if pl > 0 else '-'}{datetime.timedelta(seconds=abs(round(pl)))}"

async def stock_market_sell(user_id: int, trade_id: int) -> tuple[bool, str]:
    async with Database(DATABASE_NAME) as db:
        return await close_market_trade(db, user_id, trade_id)