"""SQLite repository and database engine for Gemini Nexus DB."""

import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional, Tuple

from gemini_nexus.core.config import DEFAULT_DB_FILE, DEFAULT_MODELS


class Database:
    """Manages SQLite database operations with WAL mode and foreign key constraints."""

    def __init__(self, db_path: str = DEFAULT_DB_FILE) -> None:
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for SQLite connections with WAL mode and PRAGMA settings."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON;")
        c.execute("PRAGMA journal_mode = WAL;")
        c.execute("PRAGMA synchronous = NORMAL;")
        c.execute("PRAGMA temp_store = MEMORY;")
        c.execute("PRAGMA busy_timeout = 5000;")
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        """Initializes database tables and default seed data."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS owners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nickname TEXT UNIQUE,
                    notes TEXT DEFAULT ''
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER,
                    key_string TEXT UNIQUE,
                    status TEXT DEFAULT 'UNCHECKED',
                    detail TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    is_ignored INTEGER DEFAULT 0,
                    FOREIGN KEY (owner_id) REFERENCES owners (id) ON DELETE CASCADE
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            # Populate default models
            for model in DEFAULT_MODELS:
                c.execute("INSERT OR IGNORE INTO models (name) VALUES (?)", (model,))

            # Seed default application settings
            default_settings = [
                ("delay_min", "7"),
                ("delay_max", "10"),
                ("current_model", DEFAULT_MODELS[0] if DEFAULT_MODELS else "gemini-3.8-flash"),
                ("proxy_use", "0"),
                ("proxy_url", "socks5://127.0.0.1:1080"),
                ("checker_threads", "1"),
                ("splitter_streams", "3"),
                ("ui_scaling", "140%"),
            ]
            for key, val in default_settings:
                c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

            conn.commit()

    def get_owners(self) -> List[Dict[str, Any]]:
        """Retrieves all owners with their active key count, sorted alphabetically."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT o.id, o.nickname, o.notes, COUNT(k.id) AS key_count
                FROM owners o
                LEFT JOIN api_keys k ON o.id = k.owner_id
                GROUP BY o.id
                ORDER BY o.nickname COLLATE NOCASE
            """)
            return [dict(row) for row in c.fetchall()]

    def add_owner(self, nickname: str, notes: str = "") -> int:
        """Adds a new owner or retrieves the existing owner ID."""
        clean_nick = nickname.strip()
        if not clean_nick:
            return -1
        with self.connect() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO owners (nickname, notes) VALUES (?, ?)",
                (clean_nick, notes.strip()),
            )
            conn.commit()
            c.execute("SELECT id FROM owners WHERE nickname=?", (clean_nick,))
            row = c.fetchone()
            return int(row["id"]) if row else -1

    def delete_owner(self, owner_id: int) -> None:
        """Deletes an owner and cascades deletion to linked api_keys."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM owners WHERE id=?", (owner_id,))
            conn.commit()

    def add_keys(self, owner_id: int, key_strings: List[str]) -> Tuple[int, int]:
        """Adds a batch of API keys for an owner, skipping duplicates."""
        added = 0
        dupes = 0
        with self.connect() as conn:
            c = conn.cursor()
            for raw_k in key_strings:
                k = raw_k.strip()
                if not k:
                    continue
                try:
                    c.execute(
                        "INSERT INTO api_keys (owner_id, key_string) VALUES (?, ?)",
                        (owner_id, k),
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    dupes += 1
            conn.commit()
        return added, dupes

    def get_keys(
        self, status_filter: str = "Все", search_query: str = ""
    ) -> List[Dict[str, Any]]:
        """Retrieves keys filtered by status and/or search query."""
        query = """
            SELECT k.id, k.owner_id, o.nickname AS owner_nickname, k.key_string,
                   k.status, k.detail, k.notes, k.is_ignored
            FROM api_keys k
            LEFT JOIN owners o ON k.owner_id = o.id
            WHERE 1=1
        """
        params: List[Any] = []
        if status_filter != "Все":
            if status_filter == "Активные (OK)":
                query += " AND k.status = 'OK'"
            elif status_filter == "Ошибки":
                query += " AND k.status NOT IN ('OK', 'UNCHECKED')"
            elif status_filter == "Игнорируемые":
                query += " AND k.is_ignored = 1"
            else:
                query += " AND k.status = ?"
                params.append(status_filter)

        search_text = search_query.strip()
        if search_text:
            query += " AND (k.key_string LIKE ? OR o.nickname LIKE ? OR k.notes LIKE ?)"
            pattern = f"%{search_text}%"
            params.extend([pattern, pattern, pattern])

        query += " ORDER BY k.id DESC"
        with self.connect() as conn:
            c = conn.cursor()
            c.execute(query, params)
            return [dict(row) for row in c.fetchall()]

    def update_key_status(self, key_id: int, status: str, detail: str = "") -> None:
        """Updates status and error details for a given key ID."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE api_keys SET status=?, detail=? WHERE id=?",
                (status, detail, key_id),
            )
            conn.commit()

    def toggle_key_ignored(self, key_id: int) -> bool:
        """Toggles the is_ignored state for a key, returning the new state."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT is_ignored FROM api_keys WHERE id=?", (key_id,))
            row = c.fetchone()
            new_state = 0 if row and row["is_ignored"] else 1
            c.execute("UPDATE api_keys SET is_ignored=? WHERE id=?", (new_state, key_id))
            conn.commit()
            return bool(new_state)

    def delete_key(self, key_id: int) -> None:
        """Deletes a single API key by its ID."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
            conn.commit()

    def reset_statuses(self, owner_id: Optional[int] = None) -> None:
        """Resets status to UNCHECKED and clears detail for all or owner-specific keys."""
        with self.connect() as conn:
            c = conn.cursor()
            if owner_id is not None:
                c.execute(
                    "UPDATE api_keys SET status='UNCHECKED', detail='' WHERE owner_id=?",
                    (owner_id,),
                )
            else:
                c.execute("UPDATE api_keys SET status='UNCHECKED', detail=''")
            conn.commit()

    def delete_broken_keys(self) -> int:
        """Deletes keys with unrecoverable / fatal error statuses, returning deleted count."""
        with self.connect() as conn:
            c = conn.cursor()
            fatal = ("FAILED_PRECONDITION", "PERMISSION_DENIED", "UNAUTHORIZED", "NOT_FOUND")
            placeholders = ",".join(["?"] * len(fatal))
            c.execute(f"DELETE FROM api_keys WHERE status IN ({placeholders})", fatal)
            deleted = c.rowcount
            conn.commit()
            return int(deleted)

    def get_models(self) -> List[str]:
        """Returns all configured Gemini model identifiers sorted by name."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM models ORDER BY name")
            return [str(row["name"]) for row in c.fetchall()]

    def add_model(self, name: str) -> bool:
        """Adds a model identifier if valid and not already existing."""
        clean = name.strip()
        if not clean:
            return False
        with self.connect() as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO models (name) VALUES (?)", (clean,))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_setting(self, key: str, default: str = "") -> str:
        """Retrieves a configuration setting by key."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = c.fetchone()
            return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Saves or updates a configuration setting."""
        with self.connect() as conn:
            c = conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )
            conn.commit()
