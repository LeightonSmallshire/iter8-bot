import sqlite3
import datetime
import logging
from typing import Dict, Optional

DATABASE_NAME = "storage.db"

def init_database(timeout_data: Dict[int, tuple[int, datetime.timedelta]]):
    with sqlite3.connect(DATABASE_NAME) as connection:
        cursor = connection.cursor()

        create_script = """
            DROP TABLE IF EXISTS timeouts
            CREATE TABLE timeouts (
                id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL,
                duration INTEGER NOT NULL
            )

            DROP TABLE IF EXISTS logs
            CREATE TABLE logs (
                id          INTEGER PRIMARY KEY,
                timestamp   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                level       TEXT NOT NULL,
                message     TEXT NOT NULL
            )
        """
        cursor.execute(create_script)

        for user_id, (total_timeouts, total_duration) in timeout_data.items():
            cursor.execute(
                "INSERT INTO timeouts (id, count, duration) VALUES (?, ?, ?)",
                (user_id, total_timeouts, total_duration.total_seconds()),
            )


def get_timeout_leaderboard() -> Dict[int, tuple[int, datetime.timedelta]]:
    with sqlite3.connect(DATABASE_NAME) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, count, duration FROM timeouts ORDER BY count, duration DESC"
        ).fetchall()
    return {
        r["id"]: (r["count"], datetime.timedelta(seconds=r["duration"]))
        for r in rows
    }


def update_timeout_leaderboard(user: int, duration: int):
    with sqlite3.connect(DATABASE_NAME) as con:
        con.execute("""
            INSERT INTO timeouts (id, count, duration)
            VALUES (?, 1, ?)
            ON CONFLICT(id) DO UPDATE SET
              count    = count + 1,
              duration = duration + excluded.duration
        """, (user, duration))


def write_log(level: str, message: str) -> None:
    with sqlite3.connect(DATABASE_NAME) as con:
        con.execute(
            "INSERT INTO logs(level, message) VALUES (?, ?)",
            (level, message),
        )

def read_logs(limit: int=100, level: Optional[str]=None):
    q = "SELECT id, ts, level, message, FROM logs"
    cond, args = [], []
    if level:
        cond.append("level = ?");  args.append(level)
    if cond:
        q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY ts DESC, id DESC LIMIT ?"; args.append(limit)

    with sqlite3.connect(DATABASE_NAME) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(q, args)]
    
def on_log(record: logging.LogRecord) -> None:
    write_log(record.levelname, record.message)