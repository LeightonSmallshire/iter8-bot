import duckdb
import logfire
import os


class Persistence:
    def __init__(self, db_path: str = "data/agent_storage.db"):
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        with logfire.span("persistence_init", db_path=db_path):
            self.conn = duckdb.connect(db_path, read_only=False)
            self._migrate()
            logfire.info("persistence_initialized", db_path=db_path)

    def _migrate(self) -> None:
        # DuckDB: Use SEQUENCE for auto-increment
        self.conn.execute("CREATE SEQUENCE IF NOT EXISTS todo_id_seq")
        self.conn.execute("CREATE SEQUENCE IF NOT EXISTS fact_id_seq")
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER DEFAULT nextval('fact_id_seq'),
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER DEFAULT nextval('todo_id_seq'),
                task TEXT,
                status TEXT DEFAULT 'pending',
                PRIMARY KEY (id)
            )
        """)
        logfire.debug("database_migrated")

    def add_todo(self, task: str) -> None:
        with logfire.span("add_todo", task=task):
            self.conn.execute("INSERT INTO todos (task) VALUES (?)", [task])
            logfire.info("todo_added", task=task)

    def get_todos(self) -> str:
        with logfire.span("get_todos"):
            rows = self.conn.execute("SELECT task FROM todos WHERE status = 'pending'").fetchall()
            result = "\n".join([f"- {r[0]}" for r in rows]) if rows else "No active tasks."
            logfire.debug("todos_retrieved", count=len(rows))
            return result

    def add_fact(self, content: str) -> None:
        with logfire.span("add_fact", content_length=len(content)):
            self.conn.execute("INSERT INTO facts (content) VALUES (?)", [content])
            logfire.info("fact_added", content_length=len(content))

    def get_facts(self) -> str:
        with logfire.span("get_facts"):
            rows = self.conn.execute("SELECT content FROM facts ORDER BY created_at DESC LIMIT 5").fetchall()
            result = "\n".join([f"- {r[0]}" for r in rows]) if rows else "No facts recorded yet."
            logfire.debug("facts_retrieved", count=len(rows))
            return result
