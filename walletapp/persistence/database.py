"""SQLite database with schema for encrypted holdings, settings, and optional private key material."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final

SCHEMA_VERSION: Final[int] = 2

DDL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY NOT NULL,
    value BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    symbol TEXT NOT NULL COLLATE NOCASE,
    balance_ciphertext BLOB NOT NULL,
    UNIQUE(kind, symbol)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY NOT NULL,
    value_ciphertext BLOB NOT NULL
);

-- Private key bytes are NEVER stored in plaintext; only ciphertext at rest.
CREATE TABLE IF NOT EXISTS wallet_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purpose TEXT NOT NULL UNIQUE,
    public_address TEXT,
    private_key_ciphertext BLOB NOT NULL
);

-- Transaction history (non-secret metadata; keys never stored here).
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    asset_kind TEXT NOT NULL,
    symbol TEXT NOT NULL COLLATE NOCASE,
    amount REAL NOT NULL,
    to_address TEXT NOT NULL,
    memo TEXT NOT NULL DEFAULT '',
    network TEXT NOT NULL,
    est_fee REAL NOT NULL DEFAULT 0.0,
    total REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'pending', -- pending|confirmed|blocked|failed
    tx_hash TEXT,
    error TEXT
);
"""


def get_default_schema_version() -> int:
    return SCHEMA_VERSION


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def init_schema(self) -> None:
        conn = self.connect()
        conn.executescript(DDL)
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION).encode("utf-8"),),
            )
            conn.commit()
            return

        # Lightweight migrations for older DBs.
        try:
            cur_version = int(bytes(row["value"]).decode("utf-8"))
        except Exception:
            cur_version = 1

        if cur_version < 2:
            # v2 introduces `transactions` history.
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    asset_kind TEXT NOT NULL,
                    symbol TEXT NOT NULL COLLATE NOCASE,
                    amount REAL NOT NULL,
                    to_address TEXT NOT NULL,
                    memo TEXT NOT NULL DEFAULT '',
                    network TEXT NOT NULL,
                    est_fee REAL NOT NULL DEFAULT 0.0,
                    total REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    tx_hash TEXT,
                    error TEXT
                );
                """
            )
            conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'schema_version'",
                (str(SCHEMA_VERSION).encode("utf-8"),),
            )
            conn.commit()

    def get_meta_blob(self, key: str) -> bytes | None:
        row = self.connect().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else row["value"]

    def set_meta_blob(self, key: str, value: bytes) -> None:
        conn = self.connect()
        conn.execute(
            """
            INSERT INTO meta (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
