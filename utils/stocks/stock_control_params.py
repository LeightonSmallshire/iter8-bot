from ..model import Stock
import math

STOCK_BASE_PRICE                = 1
STOCK_BASE_DRIFT                = 0
STOCK_BASE_VOLATILITY           = 0.005
STOCK_BASE_VOLUME               = 100

STOCK_BASE_PRICE_SPREAD         = 0.001 # 0.1%

STOCK_ACTOR_SHIFT_CORR_POWER    = 0.01
STOCK_ACTOR_SIM_SOFT_RANGE      = 1000
STOCK_ACTOR_DIR_ALTERNATOR      = 1.1

STOCK_LIQUIDITY_COFF            = 0.5

STOCK_PRICE_IMPACT              = 0.0001
STOCK_DRIFT_IMPACT              = 0.0005
STOCK_VOLATILITY_IMPACT         = 0.0005

STOCK_DECAY_FACTOR              = 0.9
STOCK_VOLUME_ALPHA              = 0.95

STOCK_SPREAD_VOLATILITY_FACTOR  = 1
STOCK_SPREAD_VOLUME_FACTOR      = 0.5



class Stocks:
    JackpotGeniusDeluxe         = Stock(None, "JackpotGeniusDeluxe",    "JGD", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME, 0, 1)
    BingoCommunity              = Stock(None, "BingoCommunity",         "BCM", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME, 0, 1)
    StarWheel                   = Stock(None, "StarWheel",              "STW", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME, 0, 1)
    SavannahFrenzy              = Stock(None, "SavannahFrenzy",         "SVF", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME, 0, 1)
    CheekyMonkeyCommunity       = Stock(None, "CheekyMonkeyCommunity",  "CMC", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME, 0, 1)
    WildDevils                  = Stock(None, "WildDevilsCommunity",    "WDC", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME, 0, 1)
    Crusher                     = Stock(None, "Crusher",                "CSH", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY, STOCK_BASE_VOLUME, 0, 1)

AVAILABLE_STOCKS: list[Stock] = [
    Stocks.JackpotGeniusDeluxe,
    Stocks.BingoCommunity,
    Stocks.StarWheel,
    Stocks.SavannahFrenzy,
    Stocks.CheekyMonkeyCommunity,
    Stocks.WildDevils,
    Stocks.Crusher,
]
