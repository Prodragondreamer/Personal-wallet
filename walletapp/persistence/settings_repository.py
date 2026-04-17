"""User preferences stored as encrypted key/value rows."""

from __future__ import annotations

import json
from typing import Any

from walletapp.persistence.database import Database
from walletapp.persistence.encryption import EncryptionService


class UserSettingsRepository:
    def __init__(self, db: Database, crypto: EncryptionService) -> None:
        self._db = db
        self._crypto = crypto

    def get_preferences(self) -> dict[str, Any]:
        conn = self._db.connect()
        rows = conn.execute("SELECT key, value_ciphertext FROM settings").fetchall()
        out: dict[str, Any] = {}
        for row in rows:
            raw = self._crypto.decrypt_text(row["value_ciphertext"])
            out[row["key"]] = json.loads(raw)
        return out

    def set_preferences(self, prefs: dict[str, Any]) -> None:
        conn = self._db.connect()
        for key, value in prefs.items():
            payload = json.dumps(value, separators=(",", ":"))
            ct = self._crypto.encrypt_text(payload)
            conn.execute(
                """
                INSERT INTO settings (key, value_ciphertext) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value_ciphertext = excluded.value_ciphertext
                """,
                (key, ct),
            )
        conn.commit()

    def set_one(self, key: str, value: Any) -> None:
        self.set_preferences({key: value})
