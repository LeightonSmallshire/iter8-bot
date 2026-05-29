import sqlite3
from datetime import datetime, timedelta
from typing import Any

import logfire
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


class AgentMemoryStore:
    def __init__(self, db_path: str = "data/agent_storage.db"):
        self.db_path = db_path
        self._saver: AsyncSqliteSaver | None = None
        self._ctx: Any | None = None

    async def get_checkpointer(self) -> AsyncSqliteSaver:
        """Returns the LangGraph checkpointer, initializing it if necessary."""
        if self._saver is None:
            self._ctx = AsyncSqliteSaver.from_conn_string(self.db_path)
            self._saver = await self._ctx.__aenter__()
        return self._saver

    async def close(self) -> None:
        """Closes the checkpointer connection."""
        if self._ctx and self._saver:
            await self._ctx.__aexit__(None, None, None)
            self._saver = None
            self._ctx = None

    def cleanup_old_checkpoints(self) -> None:
        """Prunes checkpoints older than 7 days."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Only clean up if the checkpoints table exists (first run has none)
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'"
            )
            if cursor.fetchone() is None:
                conn.close()
                return

            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute("DELETE FROM checkpoints WHERE timestamp < ?", [week_ago])
            conn.commit()
            conn.close()
            logfire.info("memory_cleanup_performed")
        except Exception as e:
            logfire.error("memory_cleanup_error", error=str(e))
