from .database import *
from typing import Optional

async def read_logs(limit: int = 100, level: Optional[str] = None):
    async with Database(DATABASE_NAME) as db:
        where = [WhereParam("level", level)] if level is not None else []
        logs = await db.select(Log, where=where, order=[OrderParam("id", True)], limit=limit)
        logs.reverse()
        return logs

