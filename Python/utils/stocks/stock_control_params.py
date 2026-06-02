from ..model import Stock

STOCK_BASE_PRICE                = 1
STOCK_BASE_DRIFT                = 0
STOCK_BASE_VOLATILITY           = 0.005
STOCK_BASE_VOLUME               = 100

STOCK_BASE_PRICE_SPREAD         = 0.001

STOCK_ACTOR_SHIFT_CORR_POWER    = 0.01
STOCK_ACTOR_SIM_SOFT_RANGE      = 1000
STOCK_ACTOR_DIR_ALTERNATOR      = 10

STOCK_LIQUIDITY_COFF            = 0.5

STOCK_PRICE_IMPACT              = 0.0001
STOCK_DRIFT_IMPACT              = 0.01
STOCK_VOLATILITY_IMPACT         = 0.01

STOCK_DECAY_FACTOR              = 0.9
STOCK_VOLUME_ALPHA              = 0.95

STOCK_SPREAD_VOLATILITY_FACTOR  = 1
STOCK_SPREAD_VOLUME_FACTOR      = 0.5


class Stocks:
    JackpotGeniusDeluxe         = Stock(name="JackpotGeniusDeluxe",    code="JGD", value=STOCK_BASE_PRICE, drift=STOCK_BASE_DRIFT, volatility=STOCK_BASE_VOLATILITY, volume=STOCK_BASE_VOLUME, volume_this_frame=0, actor_target_price=1)
    BingoCommunity              = Stock(name="BingoCommunity",         code="BCM", value=STOCK_BASE_PRICE, drift=STOCK_BASE_DRIFT, volatility=STOCK_BASE_VOLATILITY, volume=STOCK_BASE_VOLUME, volume_this_frame=0, actor_target_price=1)
    StarWheel                   = Stock(name="StarWheel",              code="STW", value=STOCK_BASE_PRICE, drift=STOCK_BASE_DRIFT, volatility=STOCK_BASE_VOLATILITY, volume=STOCK_BASE_VOLUME, volume_this_frame=0, actor_target_price=1)
    SavannahFrenzy              = Stock(name="SavannahFrenzy",         code="SVF", value=STOCK_BASE_PRICE, drift=STOCK_BASE_DRIFT, volatility=STOCK_BASE_VOLATILITY, volume=STOCK_BASE_VOLUME, volume_this_frame=0, actor_target_price=1)
    CheekyMonkeyCommunity       = Stock(name="CheekyMonkeyCommunity",  code="CMC", value=STOCK_BASE_PRICE, drift=STOCK_BASE_DRIFT, volatility=STOCK_BASE_VOLATILITY, volume=STOCK_BASE_VOLUME, volume_this_frame=0, actor_target_price=1)
    WildDevils                  = Stock(name="WildDevilsCommunity",    code="WDC", value=STOCK_BASE_PRICE, drift=STOCK_BASE_DRIFT, volatility=STOCK_BASE_VOLATILITY, volume=STOCK_BASE_VOLUME, volume_this_frame=0, actor_target_price=1)
    Crusher                     = Stock(name="Crusher",                code="CSH", value=STOCK_BASE_PRICE, drift=STOCK_BASE_DRIFT, volatility=STOCK_BASE_VOLATILITY, volume=STOCK_BASE_VOLUME, volume_this_frame=0, actor_target_price=1)

AVAILABLE_STOCKS: list[Stock] = [
    Stocks.JackpotGeniusDeluxe,
    Stocks.BingoCommunity,
    Stocks.StarWheel,
    Stocks.SavannahFrenzy,
    Stocks.CheekyMonkeyCommunity,
    Stocks.WildDevils,
    Stocks.Crusher,
]
