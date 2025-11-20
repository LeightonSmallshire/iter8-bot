from .model import Stock
import math

STOCK_BASE_PRICE        = 300
STOCK_BASE_DRIFT        = 0
STOCK_BASE_VOLATILITY   = 0.005
STOCK_BASE_VOLUME       = 100.0

STOCK_PRICE_IMPACT      = 0.0005
STOCK_DRIFT_IMPACT      = 0.000005
STOCK_VOLATILITY_IMPACT = 0.00002

STOCK_HIGH_VOLUME       = 100

STOCK_DECAY_FACTOR      = 0.99
STOCK_VOLUME_ALPHA      = 0.1

STOCK_BASE_PRICE_SPREAD = 0.001 # 0.1%

STOCK_ACTOR_SIM_COUNT   = 5

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
    vol_term = 1.0 * stock.volatility  
    liq_term = 0.25 / (stock.volume ** 1.8)

    spread = min(0.10, STOCK_BASE_PRICE_SPREAD + vol_term + liq_term)

    low = stock.value * (1 - spread)
    high = stock.value * (1 + spread)

    return low, high