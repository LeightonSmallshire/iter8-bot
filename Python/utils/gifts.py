from .database import DATABASE_NAME, Database, WhereParam
from .model import Gift


async def add_gift(gifter: int, receiver: int, value: int) -> None:
    async with Database(DATABASE_NAME) as db:
        await db.insert(Gift(amount=value, giver=gifter, receiver=receiver))


async def did_gift(gifter: int, receiver: int, value: int) -> bool:
    async with Database(DATABASE_NAME) as db:
        gifts = await db.select(Gift, where=[WhereParam("giver", gifter), WhereParam("receiver", receiver), WhereParam("amount", value)])
        return bool(gifts)
