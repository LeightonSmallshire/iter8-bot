import utils.database as database
import utils.model as model
import asyncio

async def migrate():
    async with database.Database(database.DATABASE_NAME) as db:
        await db.drop_table(model.Purchase)
        await db.create_table(model.Purchase)


asyncio.run(migrate())