from .database import *
from .shop import AdminTicketItem

async def get_extra_admin_rolls(consume: bool) -> list[int]:
    async with Database(DATABASE_NAME) as db:
        bonus_tickets = await db.select(Purchase, where=[WhereParam("item_id", AdminTicketItem.ITEM_ID), WhereParam("used", False)])

        if consume:
            await db.update(Purchase(None, None, None, None, True), where=[WhereParam("item_id", AdminTicketItem.ITEM_ID)])

        return [t.user_id for t in bonus_tickets]
    

async def get_last_admin_roll() -> Optional[Timestamps]:
    async with Database(DATABASE_NAME) as db:
        return await db.select(Timestamps)
    
async def update_last_admin_roll():
    async with Database(DATABASE_NAME) as db:
        roll_info = Timestamps(datetime.datetime.now())
        await db.insert_or_update(roll_info)
    
    
async def use_admin_reroll_token(user: int) -> tuple[bool, Optional[str]]:
    async with Database(DATABASE_NAME) as db:
        tokens = await db.select(Purchase, where=[WhereParam("item_id", AdminRerollItem.ITEM_ID), WhereParam("used", False)])
        if not tokens:
            return False, "Naughty naughty, you haven't purchased a reroll token."
        
        token = tokens[0]
        await db.update(Purchase(None, None, None, None, True), where=[WhereParam("id", token.id)])

        return True, None