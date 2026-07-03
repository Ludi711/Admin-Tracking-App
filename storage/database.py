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


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _add_column_if_missing(conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {ddl}")


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

        # Lightweight migrations for existing alpha databases.
        _add_column_if_missing(conn, "gmail_accounts", "credentials_json_encrypted", "credentials_json_encrypted TEXT")
        _add_column_if_missing(conn, "gmail_accounts", "token_storage_mode", "token_storage_mode TEXT DEFAULT 'plain_local_alpha'")
        _add_column_if_missing(conn, "gmail_accounts", "last_sync_at", "last_sync_at TEXT")
        _add_column_if_missing(conn, "gmail_accounts", "updated_at", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP")

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_items_user_status ON admin_items(user_id, status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_items_user_message ON admin_items(user_id, gmail_message_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_email_sources_user_message ON email_sources(user_id, gmail_message_id)"
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


def get_user(user_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def upsert_gmail_account(
    *,
    user_id: int,
    gmail_address: str,
    credentials_json_encrypted: str,
    token_expiry: str | None,
    token_storage_mode: str,
) -> int:
    gmail_address = gmail_address.strip().lower()
    with db_session() as conn:
        existing = conn.execute(
            "SELECT id FROM gmail_accounts WHERE user_id = ? AND gmail_address = ?",
            (user_id, gmail_address),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE gmail_accounts
                SET credentials_json_encrypted = ?, token_expiry = ?, token_storage_mode = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (credentials_json_encrypted, token_expiry, token_storage_mode, existing["id"]),
            )
            return int(existing["id"])

        cur = conn.execute(
            """
            INSERT INTO gmail_accounts
                (user_id, gmail_address, credentials_json_encrypted, token_expiry, token_storage_mode)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, gmail_address, credentials_json_encrypted, token_expiry, token_storage_mode),
        )
        return int(cur.lastrowid)


def list_gmail_accounts(user_id: int) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, gmail_address, token_expiry, token_storage_mode,
                   last_sync_at, created_at, updated_at
            FROM gmail_accounts
            WHERE user_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_primary_gmail_account(user_id: int) -> dict | None:
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT * FROM gmail_accounts
            WHERE user_id = ?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def update_gmail_last_sync(account_id: int) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE gmail_accounts SET last_sync_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (account_id,),
        )


def delete_gmail_account(account_id: int, user_id: int) -> None:
    with db_session() as conn:
        conn.execute("DELETE FROM gmail_accounts WHERE id = ? AND user_id = ?", (account_id, user_id))


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


def admin_item_exists_for_message(user_id: int, gmail_message_id: str | None) -> bool:
    if not gmail_message_id:
        return False
    with db_session() as conn:
        row = conn.execute(
            "SELECT 1 FROM admin_items WHERE user_id = ? AND gmail_message_id = ? LIMIT 1",
            (user_id, gmail_message_id),
        ).fetchone()
        return row is not None


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



def count_user_data(user_id: int) -> dict:
    """Return simple counts for the connected alpha profile."""
    with db_session() as conn:
        admin_items = conn.execute(
            "SELECT COUNT(*) AS n FROM admin_items WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"]
        email_sources = conn.execute(
            "SELECT COUNT(*) AS n FROM email_sources WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"]
        gmail_accounts = conn.execute(
            "SELECT COUNT(*) AS n FROM gmail_accounts WHERE user_id = ?",
            (user_id,),
        ).fetchone()["n"]
        return {
            "admin_items": int(admin_items),
            "email_sources": int(email_sources),
            "gmail_accounts": int(gmail_accounts),
        }


def delete_user_scanned_data(user_id: int) -> None:
    """Delete extracted admin items and saved email metadata/snippets for one alpha profile."""
    with db_session() as conn:
        conn.execute("DELETE FROM admin_items WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM email_sources WHERE user_id = ?", (user_id,))


def delete_user_gmail_credentials(user_id: int) -> None:
    """Delete saved Gmail OAuth credentials/tokens for one alpha profile."""
    with db_session() as conn:
        conn.execute("DELETE FROM gmail_accounts WHERE user_id = ?", (user_id,))


def delete_user_and_all_data(user_id: int) -> None:
    """Delete the alpha profile and all app-stored data for that profile."""
    with db_session() as conn:
        conn.execute("DELETE FROM admin_items WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM email_sources WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM gmail_accounts WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
