"""Domain errors for the wallet app."""


class VaultLockedError(RuntimeError):
    """Raised when encrypted data or signing is requested while the vault is locked."""

    pass


class VaultError(RuntimeError):
    """Raised for invalid passphrase, corrupted ciphertext, or DB issues."""

    pass
