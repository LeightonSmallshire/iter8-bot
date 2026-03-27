from .model import Gift
from .database import Database, DATABASE_NAME, WhereParam

#-----------------------------------------------------------------
#   Gifts

async def add_gift(gifter: int, receiver: int, value: int) -> None:
    async with Database(DATABASE_NAME) as db:
        await db.insert(Gift(None, value, gifter, receiver))  # type: ignore[arg-type]


async def did_gift(gifter: int, receiver: int, value: int) -> bool:
    async with Database(DATABASE_NAME) as db:
        gifts = await db.select(Gift, where=[WhereParam("giver", gifter), WhereParam("receiver", receiver), WhereParam("amount", value)])
        return bool(gifts)
