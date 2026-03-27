from .database import Database, DATABASE_NAME, WhereParam, OrderParam, WhereClause
from .model import Log
import logging
import asyncio
import datetime
from typing import Optional
    

async def write_log(level: str, message: str) -> None:
    async with Database(DATABASE_NAME) as db:
        log = Log(0, datetime.datetime.now(datetime.timezone.utc), level, message)
        await db.insert(log)

async def read_logs(limit: int = 100, level: Optional[str] = None) -> list[Log]:
    async with Database(DATABASE_NAME) as db:
        where: WhereClause = [WhereParam("level", level)] if level is not None else []
        result = await db.select(Log, where=where, order=[OrderParam("id", True)], limit=limit)
        logs = result if isinstance(result, list) else [result]
        logs.reverse()
        return logs
    
    
class DatabaseHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._run_log(record))
            else:
                loop.run_until_complete(self._run_log(record))
        except Exception:
            self.handleError(record)

    async def _run_log(self, record: logging.LogRecord) -> None:
        try:
            await write_log(record.levelname, record.getMessage())
        except Exception:
            self.handleError(record)

