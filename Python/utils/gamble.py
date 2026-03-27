from .database import Database, DATABASE_NAME, WhereParam
from .model import AdminBet, GambleWin
from typing import Any


async def record_gamble(gamble_user: int, bet_user: int, amount: float) -> int:
    async with Database(DATABASE_NAME) as db:
        gamble = AdminBet(None, amount, gamble_user, bet_user, False)  # type: ignore[arg-type]
        return await db.insert(gamble)
    
async def get_bets(user_id: int) -> dict[int, float]:
    async with Database(DATABASE_NAME) as db:
        bets = await db.select(AdminBet, where=[WhereParam("bet_user_id", user_id), WhereParam("used", False)])
        if not bets:
            return {}
        if isinstance(bets, list):
            groups: dict[int, float] = {x.gamble_user_id: 0 for x in bets}
            for x in bets:
                groups[x.gamble_user_id] += x.amount
            return groups
        return {}

def compute_betting_odds(bets: list[AdminBet]) -> dict[int, dict[str, Any]]:
    targets: dict[int, dict[str, Any]] = {}
    for b in bets:
        if b.bet_user_id not in targets:
            targets[b.bet_user_id] = {"total": 0.0, "bettors": {}}
        targets[b.bet_user_id]["total"] = targets[b.bet_user_id]["total"] + b.amount
        if b.gamble_user_id not in targets[b.bet_user_id]["bettors"]:
            targets[b.bet_user_id]["bettors"][b.gamble_user_id] = {"amount": 0.0}
        targets[b.bet_user_id]["bettors"][b.gamble_user_id]["amount"] = targets[b.bet_user_id]["bettors"][b.gamble_user_id]["amount"] + b.amount

    grand_total = sum(targets[t]["total"] for t in targets)
    if grand_total == 0:
        grand_total = 1

    for target_id, info in targets.items():
        info["odds"] = info["total"] / grand_total

        total_on_target = info["total"] or 1
        for bettor_id, binfo in info["bettors"].items():
            binfo["odds"] = binfo["amount"] / total_on_target

    return targets

async def get_gamble_odds(consume_bets: bool) -> dict[int, dict[str, Any]]:
    async with Database(DATABASE_NAME) as db:
        all_bets = await db.select(AdminBet, where=[WhereParam("used", False)])

        if consume_bets:
            await db.update(AdminBet(None, None, None, None, True))  # type: ignore[arg-type]

        bets_list: list[AdminBet] = all_bets if isinstance(all_bets, list) else []
        return compute_betting_odds(bets=bets_list)
    
async def payout_gamble(user: int, value: float) -> None:
    async with Database(DATABASE_NAME) as db:
        await db.insert(GambleWin(None, amount=value, user_id=user))  # type: ignore[arg-type]
