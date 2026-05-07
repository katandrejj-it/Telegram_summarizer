"""SQLite persistence layer for collected messages and digest run log."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent.parent / "digest.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables on first run (idempotent)."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id       INTEGER NOT NULL,
                chat_name     TEXT,
                chat_username TEXT,
                message_id    INTEGER NOT NULL,
                sender        TEXT,
                text          TEXT,
                date          TIMESTAMP NOT NULL,
                collected_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(chat_id, message_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_date ON messages(chat_id, date)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS digest_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hours_back  INTEGER,
                chats_count INTEGER,
                status      TEXT
            )
            """
        )
        conn.commit()
    logger.debug("Database initialized at %s", DB_PATH)


def save_messages(messages: list[dict[str, Any]]) -> int:
    """Persist collected messages, ignoring duplicates. Returns number inserted."""
    if not messages:
        return 0
    with _connect() as conn:
        cur = conn.executemany(
            """
            INSERT OR IGNORE INTO messages
                (chat_id, chat_name, chat_username, message_id, sender, text, date)
            VALUES
                (:chat_id, :chat_name, :chat_username, :message_id, :sender, :text, :date)
            """,
            messages,
        )
        conn.commit()
        inserted = cur.rowcount if cur.rowcount is not None else 0
    logger.info("Saved %d new messages (received %d)", inserted, len(messages))
    return inserted


def get_messages_for_digest(hours_back: int) -> dict[int, dict[str, Any]]:
    """Return messages from the last ``hours_back`` hours, grouped by chat."""
    cutoff = datetime.now(tz=timezone.utc).timestamp() - hours_back * 3600
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT chat_id, chat_name, chat_username, message_id, sender, text, date
            FROM messages
            WHERE date > datetime(?, 'unixepoch')
            ORDER BY chat_id, date
            """,
            (cutoff,),
        ).fetchall()

    chats: dict[int, dict[str, Any]] = {}
    for chat_id, chat_name, chat_username, msg_id, sender, text, date in rows:
        bucket = chats.setdefault(
            chat_id,
            {"name": chat_name, "username": chat_username, "messages": []},
        )
        bucket["messages"].append(
            {
                "message_id": msg_id,
                "sender": sender,
                "text": text,
                "date": date,
            }
        )
    return chats


def log_digest_run(hours_back: int, chats_count: int, status: str) -> None:
    """Record a digest pipeline run."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO digest_log (hours_back, chats_count, status)
            VALUES (?, ?, ?)
            """,
            (hours_back, chats_count, status),
        )
        conn.commit()
