import sqlite3
import datetime
import logging
from typing import Dict, Optional

DATABASE_NAME = "data/storage.db"

def init_database(timeout_data: Dict[int, tuple[int, datetime.timedelta]]):
    with sqlite3.connect(DATABASE_NAME) as connection:
        cursor = connection.cursor()

        create_script = """
            DROP TABLE IF EXISTS timeouts;
            CREATE TABLE timeouts (
                id INTEGER PRIMARY KEY,
                count INTEGER NOT NULL,
                duration INTEGER NOT NULL
            );

            DROP TABLE IF EXISTS logs;
            CREATE TABLE logs (
                id          INTEGER PRIMARY KEY,
                timestamp   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                level       TEXT NOT NULL,
                message     TEXT NOT NULL
            );
        """
        cursor.executescript(create_script)

        for user_id, (total_timeouts, total_duration) in timeout_data.items():
            cursor.execute(
                "INSERT INTO timeouts (id, count, duration) VALUES (?, ?, ?)",
                (user_id, total_timeouts, total_duration.total_seconds()),
            )


def get_timeout_leaderboard() -> Dict[int, tuple[int, datetime.timedelta]]:
    with sqlite3.connect(DATABASE_NAME) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id, count, duration FROM timeouts ORDER BY count DESC, duration DESC"
        ).fetchall()
    return {
        r["id"]: (r["count"], datetime.timedelta(seconds=r["duration"]))
        for r in rows
    }


def update_timeout_leaderboard(user: int, duration: int):
    with sqlite3.connect(DATABASE_NAME) as con:
        con.execute("""
            INSERT INTO timeouts (id, count, duration)
            VALUES (:id, CASE WHEN :dur > 0 THEN 1 ELSE 0 END, :dur)
            ON CONFLICT(id) DO UPDATE SET
              count    = count + CASE WHEN excluded.duration > 0 THEN 1 ELSE 0 END,
              duration = duration + excluded.duration
        """, {"id": user, "dur": duration})


def write_log(level: str, message: str) -> None:
    with sqlite3.connect(DATABASE_NAME) as con:
        con.execute(
            "INSERT INTO logs(level, message) VALUES (?, ?)",
            (level, message),
        )   

def read_logs(limit: int=100, level: Optional[str]=None):
    with sqlite3.connect(DATABASE_NAME) as con:
        con.row_factory = sqlite3.Row
        if level is None:
            sql = """
                SELECT timestamp, level, message
                FROM (
                    SELECT timestamp, level, message
                    FROM logs
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
                ORDER BY timestamp ASC
            """
            params = (limit,)
        else:
            sql = """
                SELECT timestamp, level, message
                FROM (
                    SELECT timestamp, level, message
                    FROM logs
                    WHERE level = ? COLLATE NOCASE
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
                ORDER BY timestamp ASC
            """
            params = (level, limit)

        return [dict(r) for r in con.execute(sql, params).fetchall()]