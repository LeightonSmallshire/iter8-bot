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

async def update_stock_direction(stock: Stock):
    try:
        rand_step=random.gauss(0, 0.5 )
        stock.actor_target_price *= math.pow(STOCK_ACTOR_DIR_ALTERNATOR, rand_step)
        stock.actor_target_price = min(1000,max(stock.actor_target_price, 0.0001))
    except Exception as e:
        print(e)

async def update_stocks_rand(stocks, dt):
    while dt>0:
        this_dt = min(100,dt)
        for s in stocks:
            await update_stock_rand(s, this_dt)
            await update_stock(s,this_dt)
        dt -= this_dt
    return dt

async def update_stock_rand(stock: Stock, dt):
    try:
        force_drift_power = math.log2(stock.actor_target_price)-math.log2(stock.value)
        force_drift_power *= STOCK_ACTOR_SHIFT_CORR_POWER
        force_drift = dt*random.gauss(STOCK_ACTOR_SIM_SOFT_RANGE*force_drift_power,STOCK_ACTOR_SIM_SOFT_RANGE/4)
        trade_credit = random.gauss(force_drift, math.sqrt(dt)*STOCK_ACTOR_SIM_SOFT_RANGE/2)
        trade_credit = min(3600,max(trade_credit,-3600))
        trade_count = trade_credit/stock.value
        await order_stock(stock,trade_count)
    except Exception as e:
        print(e)

def get_liquidity(vol :float):
    return math.pow(max(vol, 1),STOCK_LIQUIDITY_COFF)

def order_stock(stock: Stock, count: int):
    liquidity = get_liquidity(stock.volume)
    effective_impact = (STOCK_PRICE_IMPACT * count) / liquidity

    stock.value *= (1 + effective_impact)
    stock.volume_this_frame += count

async def update_stock(stock: Stock, dt: float):
    d_vol = stock.volume_this_frame

    vol_decay = math.pow(STOCK_VOLUME_ALPHA,dt)
    trend_decay = math.pow(STOCK_DECAY_FACTOR,dt)

    stock.volume = vol_decay * stock.volume + (1-vol_decay) * abs(d_vol**2)
    liquidity = get_liquidity(stock.volume)
    direction = 2 * d_vol / liquidity

    stock.drift = trend_decay * stock.drift + (1-trend_decay) * STOCK_DRIFT_IMPACT * direction
    stock.volatility = trend_decay*stock.volatility + (1-trend_decay) * STOCK_VOLATILITY_IMPACT * abs(direction)

    stock.drift = min(1,max(stock.drift,-1))
    stock.volatility = min(1,max(stock.volatility,0))
    # Geometric brownian motion
    mu = stock.drift
    sigma = stock.volatility
    z = random.gauss(0, 1)

    step_dir = math.exp((mu - 0.5 * sigma * sigma) * dt + sigma * math.sqrt(dt) * z);
    if(step_dir<=pow(0.5,dt) or step_dir>pow(2,dt)):
        print(f'Step_dir is too {"big" if step_dir>1 else "small"}. Step_dir:{step_dir}\t,sigma: {sigma}\t,mu: {mu}\t,dt: {dt}')
        step_dir = min(pow(1.4,dt),max(step_dir,pow(0.6,dt)))
    stock.value *= step_dir

    stock.volume_this_frame=0