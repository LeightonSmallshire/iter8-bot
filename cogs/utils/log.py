from .database import write_log
import logging
    
class DatabaseHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            write_log(record.levelname, record.getMessage())
        except Exception:
            self.handleError(record)