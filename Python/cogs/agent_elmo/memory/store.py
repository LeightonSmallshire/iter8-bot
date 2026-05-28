import sqlite3
from datetime import datetime, timedelta

import logfire
from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore


class AgentMemoryStore:
    def __init__(self, db_path: str = "data/agent_storage.db"):
        self.db_path = db_path
        self.checkpointer = SqliteSaver.from_conn_string(self.db_path)

    def get_checkpointer(self) -> SqliteSaver:
        """Returns the LangGraph checkpointer."""
        return self.checkpointer

    def cleanup_old_checkpoints(self) -> None:
        """Prunes checkpoints older than 7 days."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()

            # LangGraph checkpointers use various tables; this is a simplified
            # cleanup that targets the main checkpoint blobs
            cursor.execute("DELETE FROM checkpoints WHERE timestamp < ?", [week_ago])
            conn.commit()
            conn.close()
            logfire.info("memory_cleanup_performed")
        except Exception as e:
            logfire.error("memory_cleanup_error", error=str(e))
