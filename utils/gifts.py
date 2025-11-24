from .model import Gift
from .database import * 

#-----------------------------------------------------------------
#   Gifts

async def add_gift(gifter: int, receiver: int, value: int):
    async with Database(DATABASE_NAME) as db:
        await db.insert(Gift(None, value, gifter, receiver))


async def did_gift(gifter: int, receiver: int, value: int) -> bool:
    async with Database(DATABASE_NAME) as db:
        gifts = await db.select(Gift, where=[WhereParam("giver", gifter), WhereParam("receiver", receiver), WhereParam("amount", value)])
        return bool(gifts)
