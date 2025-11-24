from .database import *


async def record_gamble(gamble_user: int, bet_user: int, amount: float) -> int:
    async with Database(DATABASE_NAME) as db:
        gamble = AdminBet(None, amount, gamble_user, bet_user, False)
        return await db.insert(gamble)
    
async def get_bets(user_id: int) -> dict[int, float]:
    async with Database(DATABASE_NAME) as db:
        bets = await db.select(AdminBet, where=[WhereParam("bet_user_id", user_id), WhereParam("used", False)])
        groups: dict[int, float] = { x.gamble_user_id: 0 for x in bets}
        for x in bets:
            groups[x.gamble_user_id] += x.amount

        return groups
    
def compute_betting_odds(bets: list[AdminBet]):
    # aggregation structure
    targets = defaultdict(lambda: {
        "total": 0.0,
        "bettors": defaultdict(lambda: {"amount": 0.0})
    })

    # accumulate amounts
    for b in bets:
        t = targets[b.bet_user_id]
        t["total"] += b.amount
        t["bettors"][b.gamble_user_id]["amount"] += b.amount

    # compute total across all targets
    grand_total = sum(t["total"] for t in targets.values())
    if grand_total == 0:
        grand_total = 1  # avoid division by zero

    # compute odds for each target and each bettor
    for target_id, info in targets.items():
        # odds of this target winning = total bet on them / total bet overall
        info["odds"] = info["total"] / grand_total

        # odds per bettor inside this target
        total_on_target = info["total"] or 1
        for bettor_id, binfo in info["bettors"].items():
            binfo["odds"] = binfo["amount"] / total_on_target

    return targets

async def get_gamble_odds(consume_bets: bool):
    async with Database(DATABASE_NAME) as db:
        all_bets = await db.select(AdminBet, where=[WhereParam("used", False)])

        if consume_bets:
            await db.update(AdminBet(None, None, None, None, True))

        return compute_betting_odds(bets=all_bets)
    
async def payout_gamble(user: int, value: float):
    async with Database(DATABASE_NAME) as db:
        await db.insert(GambleWin(None, amount=value, user_id=user))

