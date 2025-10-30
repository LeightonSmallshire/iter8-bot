from .database import write_log
import logging
import asyncio
    
class DatabaseHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            asyncio.create_task(self._run_log(record))
        except Exception:
            self.handleError(record)

    async def _run_log(self, record: logging.LogRecord):
        try:
            await write_log(record.levelname, record.getMessage())
        except Exception:
            self.handleError(record)

