from .database import write_log
import logging
import asyncio
    
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

