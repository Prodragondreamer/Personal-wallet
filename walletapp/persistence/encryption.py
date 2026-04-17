"""
Encrypt sensitive fields at rest. Keys are derived from a user passphrase (never stored).

Private signing material is only decrypted in memory while the vault is unlocked.
"""

from __future__ import annotations

import base64
import os
from typing import Final

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from walletapp.exceptions import VaultError

# OWASP-style iteration count for PBKDF2-HMAC-SHA256 (tune for device if needed).
PBKDF2_ITERATIONS: Final[int] = 390_000
_SALT_BYTES: Final[int] = 16


def generate_salt() -> bytes:
    return os.urandom(_SALT_BYTES)


def derive_fernet_key(passphrase: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    """
    Derive a Fernet-compatible 32-byte key from passphrase + salt.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


class EncryptionService:
    """
    Symmetric encryption for SQLite BLOB columns (Fernet: AES-128-CBC + HMAC).

    TC-ES-1 (assignment): tampering ciphertext causes decrypt to fail (InvalidToken).
    """

    __slots__ = ("_fernet",)

    def __init__(self, fernet_key: bytes) -> None:
        self._fernet = Fernet(fernet_key)

    @classmethod
    def from_passphrase(cls, passphrase: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> EncryptionService:
        key = derive_fernet_key(passphrase, salt, iterations=iterations)
        return cls(key)

    def encrypt_bytes(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)

    def decrypt_bytes(self, ciphertext: bytes) -> bytes:
        try:
            return self._fernet.decrypt(ciphertext)
        except InvalidToken as e:
            raise VaultError("Decryption failed (wrong passphrase, tampered data, or corrupt DB).") from e

    def encrypt_text(self, text: str) -> bytes:
        return self.encrypt_bytes(text.encode("utf-8"))

    def decrypt_text(self, ciphertext: bytes) -> str:
        return self.decrypt_bytes(ciphertext).decode("utf-8")
