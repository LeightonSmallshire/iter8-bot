from collections import defaultdict
from typing import Any

from .database import DATABASE_NAME, Database, WhereParam
from .model import AdminBet, GambleWin


async def record_gamble(gamble_user: int, bet_user: int, amount: float) -> int:
    async with Database(DATABASE_NAME) as db:
        gamble = AdminBet(amount=amount, gamble_user_id=gamble_user, bet_user_id=bet_user)
        return await db.insert(gamble)


async def get_bets(user_id: int) -> dict[int, float]:
    async with Database(DATABASE_NAME) as db:
        bets = await db.select(AdminBet, where=[WhereParam("bet_user_id", user_id), WhereParam("used", False)])
        groups: dict[int, float] = {x.gamble_user_id: 0 for x in bets}
        for x in bets:
            groups[x.gamble_user_id] += x.amount

        return groups


def compute_betting_odds(bets: list[AdminBet]) -> dict[int, dict[str, Any]]:
    targets: dict[int, dict[str, Any]] = defaultdict(lambda: {
        "total": 0.0,
        "bettors": defaultdict(lambda: {"amount": 0.0})
    })

    for b in bets:
        t = targets[b.bet_user_id]
        t["total"] += b.amount
        t["bettors"][b.gamble_user_id]["amount"] += b.amount

    grand_total = sum(t["total"] for t in targets.values())
    if grand_total == 0:
        grand_total = 1

    for _target_id, info in targets.items():
        info["odds"] = info["total"] / grand_total

        total_on_target = info["total"] or 1
        for _bettor_id, binfo in info["bettors"].items():
            binfo["odds"] = binfo["amount"] / total_on_target

    return targets


async def get_gamble_odds(consume_bets: bool) -> dict[int, dict[str, Any]]:
    async with Database(DATABASE_NAME) as db:
        all_bets = await db.select(AdminBet, where=[WhereParam("used", False)])

        if consume_bets:
            await db.update(AdminBet(amount=0, gamble_user_id=0, bet_user_id=0, used=True))

        return compute_betting_odds(bets=all_bets)


async def payout_gamble(user: int, value: float) -> None:
    async with Database(DATABASE_NAME) as db:
        await db.insert(GambleWin(amount=value, user_id=user))
