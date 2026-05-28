import datetime
from typing import cast

from .database import DATABASE_NAME, Database, WhereParam
from .model import IsDatabaseTable, Purchase, SingleValueTable, Timestamps
from .shop import AdminRerollItem


async def get_extra_admin_rolls(consume: bool) -> list[int]:
    # async with Database(DATABASE_NAME) as db:
    #     bonus_tickets = await db.select(Purchase, where=[WhereParam("item_id", AdminTicketItem.ITEM_ID), WhereParam("used", False)])
    #
    #     if consume:
    #         await db.update(Purchase(None, None, None, True, None ), where=[WhereParam("item_id", AdminTicketItem.ITEM_ID)])
    #
    #     return [t for t in bonus_tickets if not t.used]
    return []


async def get_last_admin_roll() -> Timestamps | None:
    async with Database(DATABASE_NAME) as db:
        res = await db.select(cast(type[SingleValueTable], Timestamps))
        return cast(Timestamps, res) if res else None


async def update_last_admin_roll() -> None:
    async with Database(DATABASE_NAME) as db:
        timestamps = await get_last_admin_roll()
        if timestamps is not None:
            timestamps.last_roll = datetime.datetime.now()
            await db.update(cast(IsDatabaseTable, timestamps))
        else:
            await db.insert(cast(IsDatabaseTable, Timestamps(datetime.datetime.now(), datetime.datetime.now())))


async def use_admin_reroll_token(user: int) -> tuple[bool, str | None]:
    async with Database(DATABASE_NAME) as db:
        tokens = cast(list[Purchase], await db.select(Purchase, where=[WhereParam("item_id", AdminRerollItem.ITEM_ID), WhereParam("used", False)]))
        if not tokens:
            return False, "Naughty naughty, you haven't purchased a reroll token."

        _ = tokens[0]
        # await db.update(Purchase(None, None, None, None, True), where=[WhereParam("id", token.id)])

        return True, None
