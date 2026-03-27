from .database import Database, DATABASE_NAME, WhereParam
from .model import Timestamps, Purchase
from .shop import AdminRerollItem
from typing import Optional
import datetime


async def get_extra_admin_rolls(consume: bool) -> list[int]:
    # async with Database(DATABASE_NAME) as db:
    #     bonus_tickets = await db.select(Purchase, where=[WhereParam("item_id", AdminTicketItem.ITEM_ID), WhereParam("used", False)])
    #
    #     if consume:
    #         await db.update(Purchase(None, None, None, True, None ), where=[WhereParam("item_id", AdminTicketItem.ITEM_ID)])
    #
    #     return [t.user_id for t in bonus_tickets if not t.used]
    return []
    

async def get_last_admin_roll() -> Optional[Timestamps]:
    async with Database(DATABASE_NAME) as db:
        result = await db.select(Timestamps)  # type: ignore[type-var]
        if isinstance(result, list) and result:
            return result[0]
        return None
    
async def update_last_admin_roll() -> None:
    async with Database(DATABASE_NAME) as db:
        timestamps = await get_last_admin_roll()
        if timestamps is not None:
            timestamps.last_roll = datetime.datetime.now()
            await db.update(timestamps)  # type: ignore[type-var]
        else:
            await db.insert(Timestamps(datetime.datetime.now(), datetime.datetime.now()))  # type: ignore[type-var]    
    
async def use_admin_reroll_token(user: int) -> tuple[bool, Optional[str]]:
    async with Database(DATABASE_NAME) as db:
        tokens = await db.select(Purchase, where=[WhereParam("item_id", AdminRerollItem.ITEM_ID), WhereParam("used", False)])
        if not tokens:
            return False, "Naughty naughty, you haven't purchased a reroll token."
        
        if not (isinstance(tokens, list) and tokens):
            return False, "Naughty naughty, you haven't purchased a reroll token."

        return True, None
    