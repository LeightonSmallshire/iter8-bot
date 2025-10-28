from .database import write_log
import logging
    
def on_log(record: logging.LogRecord) -> None:
    write_log(record.levelname, record.getMessage())

class DatabaseHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            on_log(record)
        except Exception:
            self.handleError(record)