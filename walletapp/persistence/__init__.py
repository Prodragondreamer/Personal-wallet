"""Local persistence: SQLite + encrypted sensitive fields (assignment: Doyle / Local Persistence)."""

from walletapp.persistence.database import Database, get_default_schema_version
from walletapp.persistence.encryption import EncryptionService
from walletapp.persistence.settings_repository import UserSettingsRepository
from walletapp.persistence.wallet_repository import WalletRepository

__all__ = [
    "Database",
    "EncryptionService",
    "UserSettingsRepository",
    "WalletRepository",
    "get_default_schema_version",
]
