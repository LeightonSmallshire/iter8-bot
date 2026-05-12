from .database import DATABASE_NAME, Database, OrderParam, WhereParam
from .model import Log


async def read_logs(limit: int = 100, level: str | None = None) -> list[Log]:
    async with Database(DATABASE_NAME) as db:
        where = [WhereParam("level", level)] if level is not None else []
        logs = await db.select(Log, where=where, order=[OrderParam("id", True)], limit=limit)
        logs.reverse()
        return logs
