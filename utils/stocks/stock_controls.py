import random
from utils.stocks.stock_control_params import *
from ..model import Stock
import math


def calculate_buy_sell_price(stock: Stock) -> tuple[float, float]:
    # low liquidity widens spreads (inverse of volume)
    vol_term = STOCK_SPREAD_VOLATILITY_FACTOR * stock.volatility  
    liq_term = 2 / (stock.volume ** STOCK_SPREAD_VOLUME_FACTOR)

    spread = min(0.10, STOCK_BASE_PRICE_SPREAD + vol_term + liq_term)

    low = stock.value * (1 - spread)
    high = stock.value * (1 + spread)

    return low, high

async def update_stocks_rand(stocks):
    updated_stock = set();
    for _ in range(STOCK_ACTOR_SIM_COUNT):
        stock=random.choice(stocks)
        updated_stock.add(stock)
        update_stock_rand(random.choice(stocks))

async def update_stock_rand(stock: Stock):
    trade_count = random.randint(-STOCK_ACTOR_SIM_BUY_RANGE, STOCK_ACTOR_SIM_BUY_RANGE)
    update_stock(stock,trade_count)

async def update_stock(stock: Stock, count: int):
    # EMA smoothing
    stock.volume = (1 - STOCK_VOLUME_ALPHA) * stock.volume + STOCK_VOLUME_ALPHA * abs(count)

    liquidity = math.sqrt(max(stock.volume, 1))
    effective_impact = (STOCK_PRICE_IMPACT * count) / liquidity

    stock.value *= (1 + effective_impact)
    stock.drift += STOCK_DRIFT_IMPACT * count / liquidity
    stock.volatility += abs(count) * STOCK_VOLATILITY_IMPACT / liquidity
    stock.volatility = max(0.0001, min(stock.volatility, 1.0))

async def post_update_stock(stock: Stock, dt: float):
    mu = stock.drift
    sigma = stock.volatility
    z = random.gauss(0, 1)

    stock.value *= math.exp((mu - 0.5 * sigma * sigma) * dt +
                            sigma * math.sqrt(dt) * z)
    
    quiet_factor = max(STOCK_DECAY_FACTOR, 1 - stock.volume / 10000)

    stock.drift *= quiet_factor
    stock.volatility = STOCK_BASE_VOLATILITY + (stock.volatility - STOCK_BASE_VOLATILITY) * quiet_factor

    # clamp vol to avoid collapse or explosion
    stock.volatility = max(0.001, min(stock.volatility, 1.0))