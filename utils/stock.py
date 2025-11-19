from .model import Stock

STOCK_BASE_PRICE        = 300
STOCK_BASE_DRIFT        = 0
STOCK_BASE_VOLATILITY   = 0.005

STOCK_PRICE_IMPACT      = 0.0002
STOCK_DRIFT_IMPACT      = 0.000005
STOCK_VOLATILITY_IMPACT = 0.00001

STOCK_DECAY_FACTOR      = 0.99

class Stocks:
    JackpotGeniusDeluxe         = Stock(None, "JackpotGeniusDeluxe",    "JGD", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY)
    BingoCommunity              = Stock(None, "BingoCommunity",         "BCM", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY)
    StarWheel                   = Stock(None, "StarWheel",              "STW", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY)
    SavannahFrenzy              = Stock(None, "SavannahFrenzy",         "SVF", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY)
    CheekyMonkeyCommunity       = Stock(None, "CheekyMonkeyCommunity",  "CMC", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY)
    WildDevils                  = Stock(None, "WildDevilsCommunity",    "WDC", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY)
    Crusher                     = Stock(None, "Crusher",                "CSH", STOCK_BASE_PRICE, STOCK_BASE_DRIFT, STOCK_BASE_VOLATILITY)

AVAILABLE_STOCKS: list[Stock] = [
    Stocks.JackpotGeniusDeluxe,
    Stocks.BingoCommunity,
    Stocks.StarWheel,
    Stocks.SavannahFrenzy,
    Stocks.CheekyMonkeyCommunity,
    Stocks.WildDevils,
    Stocks.Crusher,
]