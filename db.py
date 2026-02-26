"""
Database layer — SQLite for message storage, scheduling, etc.
"""

import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional


DB_PATH = os.environ.get("DB_PATH", "tldr_bot.db")


class Database:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id     INTEGER NOT NULL,
                    user_id     INTEGER NOT NULL,
                    username    TEXT,
                    text        TEXT NOT NULL,
                    timestamp   DATETIME NOT NULL,
                    message_id  INTEGER,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_messages_chat_ts
                    ON messages (chat_id, timestamp);

                CREATE INDEX IF NOT EXISTS idx_messages_chat_user
                    ON messages (chat_id, username);

                CREATE TABLE IF NOT EXISTS schedules (
                    chat_id     INTEGER PRIMARY KEY,
                    time_str    TEXT NOT NULL,
                    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

    # ──────────────────────────────────────────
    # Messages
    # ──────────────────────────────────────────

    def store_message(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        text: str,
        timestamp: datetime,
        message_id: int,
    ):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO messages (chat_id, user_id, username, text, timestamp, message_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (chat_id, user_id, username, text, timestamp.isoformat(), message_id),
            )

    def get_messages(
        self, chat_id: int, hours: int = 24
    ) -> List[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT username, text, timestamp
                   FROM messages
                   WHERE chat_id = ? AND timestamp >= ?
                   ORDER BY timestamp ASC""",
                (chat_id, cutoff.isoformat()),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_user_messages(
        self, chat_id: int, username: str, limit: int = 100
    ) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT username, text, timestamp
                   FROM messages
                   WHERE chat_id = ? AND LOWER(username) = LOWER(?)
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (chat_id, username, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────
    # Schedules
    # ──────────────────────────────────────────

    def save_schedule(self, chat_id: int, time_str: str):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO schedules (chat_id, time_str, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(chat_id) DO UPDATE SET
                       time_str = excluded.time_str,
                       updated_at = CURRENT_TIMESTAMP""",
                (chat_id, time_str),
            )

    def get_schedule(self, chat_id: int) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT time_str FROM schedules WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        return row["time_str"] if row else None

    def remove_schedule(self, chat_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM schedules WHERE chat_id = ?", (chat_id,))

    def get_all_schedules(self) -> List[Tuple[int, str]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT chat_id, time_str FROM schedules").fetchall()
        return [(r["chat_id"], r["time_str"]) for r in rows]
