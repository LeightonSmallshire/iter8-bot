import random
from utils.stocks.stock_control_params import *
from ..model import Stock
import math


def calculate_buy_sell_price(stock: Stock) -> tuple[float, float]:
    # low liquidity widens spreads (inverse of volume)
    market_term = STOCK_SPREAD_VOLATILITY_FACTOR * stock.volatility / (stock.volume ** STOCK_SPREAD_VOLUME_FACTOR)

    spread = min(0.10, STOCK_BASE_PRICE_SPREAD + market_term)

    low = stock.value * (1 - spread)
    high = stock.value * (1 + spread)

    return low, high

async def update_stocks_rand(stocks):
    for _ in range(STOCK_ACTOR_SIM_COUNT):
        await update_stock_rand(random.choice(stocks))

async def update_stock_rand(stock: Stock):
    try:
        force_drift_power = -math.log2(stock.value)*STOCK_ACTOR_SHIFT_CORR_POWER
        force_drift = random.gauss(STOCK_ACTOR_SIM_SOFT_RANGE*force_drift_power/10,STOCK_ACTOR_SIM_SOFT_RANGE/4)
        trade_credit = random.gauss(force_drift, STOCK_ACTOR_SIM_SOFT_RANGE/2)
        trade_credit = min(3600,max(trade_credit,-3600))
        trade_count = trade_credit/stock.value
        await order_stock(stock,trade_count)
    except Exception as e:
        print(e)

def get_liquidity(vol :float):
    return math.pow(max(vol, 1),STOCK_LIQUIDITY_COFF)

async def order_stock(stock: Stock, count: int):
    liquidity = get_liquidity(stock.volume)
    effective_impact = (STOCK_PRICE_IMPACT * count) / liquidity

    stock.value *= (1 + effective_impact)
    stock.volume_this_frame += count

async def update_stock(stock: Stock, dt: float):
    d_vol = stock.volume_this_frame

    stock.volume = STOCK_VOLUME_ALPHA * stock.volume + (1-STOCK_VOLUME_ALPHA) * abs(d_vol**2)
    liquidity = get_liquidity(stock.volume)
    direction = 2 * d_vol / liquidity

    stock.drift = STOCK_DECAY_FACTOR * stock.drift + (1-STOCK_DECAY_FACTOR) * STOCK_DRIFT_IMPACT * direction
    stock.volatility = STOCK_DECAY_FACTOR*stock.volatility + (1-STOCK_DECAY_FACTOR) * STOCK_VOLATILITY_IMPACT * abs(direction)

    # Geometric brownian motion
    mu = stock.drift
    sigma = stock.volatility
    z = random.gauss(0, 1)

    step_dir = math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * math.sqrt(dt) * z);
    if(step_dir<=0.5 or step_dir>2):
        print(f'Step_dir is weird again. Step_dir:{step_dir}\t,sigma: {sigma}\t,mu: {mu}\t,dt: {dt}')
        stock.value *= step_dir
    step_dir = min(2,max(step_dir,0.5))

    stock.volume_this_frame=0