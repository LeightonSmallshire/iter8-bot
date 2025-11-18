from .model import Stock

STOCK_PRICE_IMPACT = 0.0001
STOCK_DRIFT_IMPACT = 0.0000005
STOCK_VOLATILITY_IMPACT = 0.00001

class Stocks:
    JackpotGeniusDeluxe         = Stock(None, "JackpotGeniusDeluxe",    "JGD", 300, 0.0001, 0.002)
    BingoCommunity              = Stock(None, "BingoCommunity",         "BCM", 300, 0.0001, 0.002)
    StarWheel                   = Stock(None, "StarWheel",              "STW", 300, 0.0001, 0.002)
    SavannahFrenzy              = Stock(None, "SavannahFrenzy",         "SVF", 300, 0.0001, 0.002)
    CheekyMonkeyCommunity       = Stock(None, "CheekyMonkeyCommunity",  "CMC", 300, 0.0001, 0.002)
    WildDevils                  = Stock(None, "WildDevilsCommunity",    "WDC", 300, 0.0001, 0.002)
    Crusher                     = Stock(None, "Crusher",                "CSH", 300, 0.0001, 0.002)

AVAILABLE_STOCKS: list[Stock] = [
    Stocks.JackpotGeniusDeluxe,
    Stocks.BingoCommunity,
    Stocks.StarWheel,
    Stocks.SavannahFrenzy,
    Stocks.CheekyMonkeyCommunity,
    Stocks.WildDevils,
    Stocks.Crusher,
]