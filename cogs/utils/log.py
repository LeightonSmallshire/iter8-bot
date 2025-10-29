from .database import write_log
import logging
import asyncio
    
class DatabaseHandler(logging.Handler):
    def __init__(self, loop):
        self.loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        try:
            fut = asyncio.run_coroutine_threadsafe(write_log(record.levelname, record.getMessage()), self.loop)
            fut.result()
        except Exception:
            self.handleError(record)
