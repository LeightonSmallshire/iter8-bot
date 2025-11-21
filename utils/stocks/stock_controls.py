import random
from utils.stocks.stock_control_params import *
from ..model import Stock
import math


def calculate_buy_sell_price(stock: Stock) -> tuple[float, float]:
    # low liquidity widens spreads (inverse of volume)
    market_term = STOCK_SPREAD_VOLATILITY_FACTOR * stock.volatility  / (stock.volume ** STOCK_SPREAD_VOLUME_FACTOR)

    spread = min(0.10, STOCK_BASE_PRICE_SPREAD + market_term)

    low = stock.value * (1 - spread)
    high = stock.value * (1 + spread)

    return low, high

async def update_stocks_rand(stocks):
    updated_stock = set();
    for _ in range(STOCK_ACTOR_SIM_COUNT):
        stock=random.choice(stocks)
        updated_stock.add(stock)
        update_stock_rand(stock)
    return updated_stock

async def update_stock_rand(stock: Stock):
    trade_count = stock.value /random.gauss(-STOCK_ACTOR_SIM_BUY_RANGE, STOCK_ACTOR_SIM_BUY_RANGE)
    order_stock(stock,trade_count)

async def order_stock(stock: Stock, count: int):
    liquidity = math.sqrt(max(stock.volume, 1))
    effective_impact = (STOCK_PRICE_IMPACT * count) / liquidity

    stock.value *= (1 + effective_impact)
    stock.volume_this_frame += count

async def update_stock(stock: Stock, dt: float):
    d_vol = stock.volume_this_frame

    stock.volume = (1 - STOCK_VOLUME_ALPHA) * stock.volume + STOCK_VOLUME_ALPHA * abs(d_vol)
    liquidity = math.sqrt(max(stock.volume, 1))
    direction = d_vol / liquidity

    stock.drift = STOCK_DECAY_FACTOR * stock.drift + (1-STOCK_DECAY_FACTOR) * STOCK_DRIFT_IMPACT * direction
    stock.volatility = STOCK_DECAY_FACTOR*stock.volatility + (1-STOCK_DECAY_FACTOR) * (abs(direction) * STOCK_VOLATILITY_IMPACT) 

    # Geometric brownian motion
    mu = stock.drift
    sigma = stock.volatility
    z = random.gauss(0, 1)

    stock.value *= math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * math.sqrt(dt) * z)

    stock.volume_this_frame=0