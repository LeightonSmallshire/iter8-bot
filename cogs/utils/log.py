from .database import write_log
import logging
import asyncio
    
class DatabaseHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            asyncio.create_task(write_log(record.levelname, record.getMessage()))
        except Exception:
            self.handleError(record)
