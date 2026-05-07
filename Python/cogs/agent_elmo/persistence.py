import sqlite3
import logfire
import os
from typing import List, Optional
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, ModelMessagesTypeAdapter


class Persistence:
    def __init__(self, db_path: str = "data/agent_storage.db"):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        with logfire.span("persistence_init", db_path=db_path):
            self.db_path = db_path
            self._migrate()
            logfire.info("persistence_initialized", db_path=db_path)

    def _get_connection(self):
        """Get a new connection for thread safety."""
        return sqlite3.connect(self.db_path)

    def _migrate(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create tables with SQLite syntax
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER NOT NULL,
                message_data BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        logfire.debug("database_migrated")

    def add_todo(self, task: str) -> None:
        with logfire.span("add_todo", task=task):
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO todos (task) VALUES (?)", [task])
            conn.commit()
            conn.close()
            logfire.info("todo_added", task=task)

    def get_todos(self) -> str:
        with logfire.span("get_todos"):
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT task FROM todos WHERE status = 'pending'")
            rows = cursor.fetchall()
            conn.close()
            result = "\n".join([f"- {r[0]}" for r in rows]) if rows else "No active tasks."
            logfire.debug("todos_retrieved", count=len(rows))
            return result

    def add_fact(self, content: str) -> None:
        with logfire.span("add_fact", content_length=len(content)):
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO facts (content) VALUES (?)", [content])
            conn.commit()
            conn.close()
            logfire.info("fact_added", content_length=len(content))

    def get_facts(self) -> str:
        with logfire.span("get_facts"):
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM facts ORDER BY created_at DESC LIMIT 5")
            rows = cursor.fetchall()
            conn.close()
            result = "\n".join([f"- {r[0]}" for r in rows]) if rows else "No facts recorded yet."
            logfire.debug("facts_retrieved", count=len(rows))
            return result

    def save_message_history(self, channel_id: int, messages: List[ModelMessage]) -> None:
        """Save message history for a channel."""
        with logfire.span("save_message_history", channel_id=channel_id, count=len(messages)):
            # Serialize messages to JSON using ModelMessagesTypeAdapter
            data_json = ModelMessagesTypeAdapter.dump_json(messages)
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Delete old history and insert new
            cursor.execute("DELETE FROM message_history WHERE channel_id = ?", [channel_id])
            cursor.execute(
                "INSERT INTO message_history (channel_id, message_data) VALUES (?, ?)",
                [channel_id, data_json]
            )
            
            conn.commit()
            conn.close()
            logfire.info("message_history_saved", channel_id=channel_id, count=len(messages))

    def load_message_history(self, channel_id: int) -> List[ModelMessage]:
        """Load message history for a channel."""
        with logfire.span("load_message_history", channel_id=channel_id):
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT message_data FROM message_history WHERE channel_id = ? ORDER BY created_at DESC LIMIT 1",
                [channel_id]
            )
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return []
            
            try:
                # Deserialize messages using ModelMessagesTypeAdapter
                messages = ModelMessagesTypeAdapter.validate_json(rows[0][0])
                logfire.debug("message_history_loaded", channel_id=channel_id, count=len(messages))
                return messages
            except Exception as e:
                logfire.error("message_history_load_error", error=str(e))
                return []

    def compact_history(self, channel_id: int, max_messages: int = 10) -> List[ModelMessage]:
        """Compact message history by keeping only the most recent messages."""
        with logfire.span("compact_history", channel_id=channel_id, max_messages=max_messages):
            messages = self.load_message_history(channel_id)
            if len(messages) <= max_messages:
                return messages
            
            # Keep only the most recent messages
            compacted = messages[-max_messages:]
            self.save_message_history(channel_id, compacted)
            logfire.info("history_compacted", channel_id=channel_id, 
                        original_count=len(messages), new_count=len(compacted))
            return compacted
