"""
Store optional Ethereum-style private key material encrypted at rest.

The cleartext private key only exists in memory when explicitly decrypted for signing.
For the MVP UI stub, we generate and persist test key bytes so the storage path is real;
actual Web3 signing can plug in later without changing the encryption model.
"""

from __future__ import annotations

import os

from walletapp.persistence.database import Database
from walletapp.persistence.encryption import EncryptionService


class EncryptedKeyStore:
    def __init__(self, db: Database, crypto: EncryptionService) -> None:
        self._db = db
        self._crypto = crypto

    def has_key(self, purpose: str) -> bool:
        conn = self._db.connect()
        row = conn.execute(
            "SELECT 1 FROM wallet_keys WHERE purpose = ? LIMIT 1",
            (purpose,),
        ).fetchone()
        return row is not None

    def get_public_address(self, purpose: str) -> str | None:
        conn = self._db.connect()
        row = conn.execute(
            "SELECT public_address FROM wallet_keys WHERE purpose = ?",
            (purpose,),
        ).fetchone()
        if row is None:
            return None
        return row["public_address"]

    def get_private_key_bytes(self, purpose: str) -> bytes:
        """Decrypt private key into memory. Caller must clear buffers when done."""
        conn = self._db.connect()
        row = conn.execute(
            "SELECT private_key_ciphertext FROM wallet_keys WHERE purpose = ?",
            (purpose,),
        ).fetchone()
        if row is None:
            raise KeyError(f"No encrypted key for purpose={purpose!r}")
        return self._crypto.decrypt_bytes(row["private_key_ciphertext"])

    def ensure_test_key(self, purpose: str = "sepolia_demo") -> tuple[str, bytes]:
        """
        Create a random 32-byte key if missing; return (hex_address_placeholder, key_bytes).

        Address is a non-sensitive label for UI; real address should come from eth_account later.
        """
        conn = self._db.connect()
        row = conn.execute(
            "SELECT public_address, private_key_ciphertext FROM wallet_keys WHERE purpose = ?",
            (purpose,),
        ).fetchone()
        if row is not None:
            key_bytes = self._crypto.decrypt_bytes(row["private_key_ciphertext"])
            addr = row["public_address"] or ""
            return addr, key_bytes

        key_bytes = os.urandom(32)
        ct = self._crypto.encrypt_bytes(key_bytes)
        # Placeholder "address" — not derived from key until Web3 is wired.
        addr = "0x" + key_bytes.hex()[:40]
        conn.execute(
            """
            INSERT INTO wallet_keys (purpose, public_address, private_key_ciphertext)
            VALUES (?, ?, ?)
            """,
            (purpose, addr, ct),
        )
        conn.commit()
        return addr, key_bytes
