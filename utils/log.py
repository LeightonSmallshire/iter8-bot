from .database import *
import logging
import asyncio
    

async def write_log(level: str, message: str) -> None:
    async with Database(DATABASE_NAME) as db:
        log = Log(None, datetime.datetime.now(datetime.timezone.utc), level, message)
        await db.insert(log)

async def read_logs(limit: int=100, level: Optional[str]=None):
    async with Database(DATABASE_NAME) as db:
        where = [WhereParam("level", level)] if level is not None else []
        logs = await db.select(Log, where=where, order=[OrderParam("id", True)], limit=limit)
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

    async def _run_log(self, record: logging.LogRecord):
        try:
            await write_log(record.levelname, record.getMessage())
        except Exception:
            self.handleError(record)

