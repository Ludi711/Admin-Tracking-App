from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from config import DB_PATH


def get_connection(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_session(db_path: Path | str = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db_session() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                display_name TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS gmail_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gmail_address TEXT NOT NULL,
                access_token_encrypted TEXT,
                refresh_token_encrypted TEXT,
                token_expiry TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS email_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gmail_message_id TEXT,
                thread_id TEXT,
                sender TEXT,
                subject TEXT,
                received_at TEXT,
                snippet TEXT,
                source_type TEXT DEFAULT 'csv_import',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, gmail_message_id)
            );

            CREATE TABLE IF NOT EXISTS admin_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email_source_id INTEGER,
                gmail_message_id TEXT,
                source_name TEXT,
                subject TEXT,
                admin_type TEXT,
                description TEXT,
                due_date TEXT,
                amount REAL,
                urgency_score INTEGER DEFAULT 50,
                confidence_score REAL DEFAULT 0.50,
                status TEXT DEFAULT 'needs_review',
                review_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (email_source_id) REFERENCES email_sources(id)
            );
            """
        )


def get_or_create_user(email: str, display_name: Optional[str] = None) -> int:
    email = email.strip().lower()
    if not email:
        raise ValueError("User email cannot be blank")
    with db_session() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            return int(existing["id"])
        cur = conn.execute(
            "INSERT INTO users (email, display_name) VALUES (?, ?)",
            (email, display_name or email),
        )
        return int(cur.lastrowid)


def list_users() -> list[dict]:
    with db_session() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def insert_email_source(
    *,
    user_id: int,
    gmail_message_id: str | None,
    thread_id: str | None,
    sender: str | None,
    subject: str | None,
    received_at: str | None,
    snippet: str | None,
    source_type: str = "csv_import",
) -> int:
    with db_session() as conn:
        if gmail_message_id:
            existing = conn.execute(
                "SELECT id FROM email_sources WHERE user_id = ? AND gmail_message_id = ?",
                (user_id, gmail_message_id),
            ).fetchone()
            if existing:
                return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO email_sources
                (user_id, gmail_message_id, thread_id, sender, subject, received_at, snippet, source_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, gmail_message_id, thread_id, sender, subject, received_at, snippet, source_type),
        )
        return int(cur.lastrowid)


def insert_admin_item(item: dict) -> int:
    with db_session() as conn:
        cur = conn.execute(
            """
            INSERT INTO admin_items
                (user_id, email_source_id, gmail_message_id, source_name, subject, admin_type,
                 description, due_date, amount, urgency_score, confidence_score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.get("user_id"),
                item.get("email_source_id"),
                item.get("gmail_message_id"),
                item.get("source_name"),
                item.get("subject"),
                item.get("admin_type"),
                item.get("description"),
                item.get("due_date"),
                item.get("amount"),
                item.get("urgency_score", 50),
                item.get("confidence_score", 0.5),
                item.get("status", "needs_review"),
            ),
        )
        return int(cur.lastrowid)


def fetch_admin_items(user_id: int, status: str | None = None) -> list[dict]:
    query = "SELECT * FROM admin_items WHERE user_id = ?"
    params: list = [user_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY urgency_score DESC, due_date ASC, created_at DESC"
    with db_session() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def update_admin_item_status(item_id: int, status: str, review_notes: str | None = None) -> None:
    with db_session() as conn:
        conn.execute(
            """
            UPDATE admin_items
            SET status = ?, review_notes = COALESCE(?, review_notes), updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, review_notes, item_id),
        )


def update_admin_item_fields(item_id: int, fields: dict) -> None:
    allowed = {
        "source_name", "admin_type", "description", "due_date", "amount",
        "urgency_score", "confidence_score", "status", "review_notes"
    }
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return
    assignments = ", ".join([f"{key} = ?" for key in clean])
    values = list(clean.values()) + [item_id]
    with db_session() as conn:
        conn.execute(
            f"UPDATE admin_items SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
