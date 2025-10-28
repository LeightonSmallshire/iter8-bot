import database
import logging
    
def on_log(record: logging.LogRecord) -> None:
    database.write_log(record.levelname, record.message)

class CallbackHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            on_log(record)
        except Exception:
            self.handleError(record)