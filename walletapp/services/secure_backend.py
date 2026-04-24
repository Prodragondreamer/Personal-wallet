from __future__ import annotations

from walletapp.exceptions import VaultError
from walletapp.models import Asset, AssetKind, TransactionDraft, TransactionPreview
from walletapp.persistence.database import Database
from walletapp.persistence.encryption import PBKDF2_ITERATIONS, EncryptionService, generate_salt
from walletapp.persistence.key_store import EncryptedKeyStore
from walletapp.persistence.settings_repository import UserSettingsRepository
from walletapp.persistence.transaction_repository import TransactionRepository, TransactionRecord
from walletapp.persistence.wallet_repository import WalletRepository
from walletapp.services.backend import BackendController, SendResult
from walletapp.services.market_service import MarketService

_UNLOCK_TOKEN = b"personal_wallet_mvp_unlock_v1"


class SecureWalletBackend(BackendController):
    def __init__(self, db_path: str) -> None:
        self._db = Database(db_path)
        self._db.init_schema()
        self._tx = TransactionRepository(self._db)
        self._crypto: EncryptionService | None = None
        self._wallet: WalletRepository | None = None
        self._settings: UserSettingsRepository | None = None
        self._keys: EncryptedKeyStore | None = None
        self._market = MarketService()

    @property
    def is_unlocked(self) -> bool:
        return self._crypto is not None

    def vault_exists(self) -> bool:
        return self._db.get_meta_blob("salt") is not None

    def _bind_repos(self) -> None:
        assert self._crypto is not None
        self._wallet = WalletRepository(self._db, self._crypto)
        self._settings = UserSettingsRepository(self._db, self._crypto)
        self._keys = EncryptedKeyStore(self._db, self._crypto)

    def _clear_unlock(self) -> None:
        self._crypto = None
        self._wallet = None
        self._settings = None
        self._keys = None

    def initialize_vault(self, passphrase: str) -> None:
        if len(passphrase) < 8:
            raise VaultError("Passphrase must be at least 8 characters.")
        if self.vault_exists():
            raise VaultError("Vault already initialized. Unlock instead.")
        salt = generate_salt()
        crypto = EncryptionService.from_passphrase(passphrase, salt)
        token = crypto.encrypt_bytes(_UNLOCK_TOKEN)
        self._db.set_meta_blob("salt", salt)
        self._db.set_meta_blob("kdf_iterations", str(PBKDF2_ITERATIONS).encode())
        self._db.set_meta_blob("unlock_check", token)
        self._crypto = crypto
        self._bind_repos()
        assert self._wallet is not None
        self._wallet.save_holdings(
            [
                Asset(kind=AssetKind.CRYPTO, symbol="ETH", balance=1.234),
                Asset(kind=AssetKind.CRYPTO, symbol="USDC", balance=250.00),
                Asset(kind=AssetKind.STOCK, symbol="AAPL", balance=3.0),
            ]
        )
        assert self._keys is not None
        self._keys.ensure_test_key("sepolia_demo")
        self._settings.set_preferences(
            {
                "killswitch_enabled": False,
                "require_pin": False,
                "biometrics": False,
            }
        )

    def unlock(self, passphrase: str) -> bool:
        salt = self._db.get_meta_blob("salt")
        if salt is None:
            return False
        raw_iters = self._db.get_meta_blob("kdf_iterations")
        iterations = int(raw_iters.decode("utf-8")) if raw_iters else 390_000
        try:
            crypto = EncryptionService.from_passphrase(passphrase, salt, iterations=iterations)
        except Exception:
            return False
        check = self._db.get_meta_blob("unlock_check")
        if check is None:
            return False
        try:
            pt = crypto.decrypt_bytes(check)
        except VaultError:
            return False
        if pt != _UNLOCK_TOKEN:
            return False
        self._crypto = crypto
        self._bind_repos()
        return True

    def lock(self) -> None:
        self._clear_unlock()

    def load_security_settings(self) -> dict[str, bool]:
        if not self.is_unlocked or self._settings is None:
            return {"killswitch_enabled": False, "require_pin": False, "biometrics": False}
        prefs = self._settings.get_preferences()
        return {
            "killswitch_enabled": bool(prefs.get("killswitch_enabled", False)),
            "require_pin": bool(prefs.get("require_pin", False)),
            "biometrics": bool(prefs.get("biometrics", False)),
        }

    def save_security_settings(self, killswitch: bool, require_pin: bool, biometrics: bool) -> None:
        if not self.is_unlocked or self._settings is None:
            raise VaultError("Vault is locked.")
        self._settings.set_preferences(
            {
                "killswitch_enabled": killswitch,
                "require_pin": require_pin,
                "biometrics": biometrics,
            }
        )

    def list_assets(self) -> list[Asset]:
        if not self.is_unlocked or self._wallet is None:
            return []
        try:
            return self._wallet.get_holdings()
        except VaultError:
            return []

    def credit_asset(self, kind: AssetKind, symbol: str, amount: float) -> None:
        """
        Add funds to a holding (demo/top-up). Persists to the encrypted DB.
        """
        if not self.is_unlocked or self._wallet is None:
            raise VaultError("Vault is locked.")
        symbol = (symbol or "").strip().upper()
        if not symbol:
            raise VaultError("Missing symbol.")
        amt = float(amount)
        if amt <= 0:
            raise VaultError("Amount must be greater than 0.")

        # Find existing balance (if any) and add.
        cur_bal = 0.0
        try:
            for a in self._wallet.get_holdings():
                if a.symbol.upper() == symbol and a.kind == kind:
                    cur_bal = float(a.balance)
                    break
        except VaultError:
            cur_bal = 0.0

        self._wallet.replace_symbol_balance(symbol, cur_bal + amt, kind)

    def get_portfolio_total_usd(self) -> float:
        if not self.is_unlocked or self._wallet is None:
            return 0.0
        try:
            holdings = self._wallet.get_holdings()
        except VaultError:
            return 0.0
        total = 0.0
        for a in holdings:
            price = self._market.get_price(a.symbol, a.kind.value)
            total += float(a.balance) * float(price)
        return total

    def preview_transaction(self, draft: TransactionDraft) -> TransactionPreview:
        if not self.is_unlocked:
            est_fee = 0.0
            return TransactionPreview(
                draft=draft,
                network="Locked",
                est_fee=est_fee,
                total=float(draft.amount) + est_fee,
            )
        ks = self.load_security_settings()
        if ks["killswitch_enabled"]:
            return TransactionPreview(
                draft=draft,
                network="Testnet (blocked)",
                est_fee=0.0,
                total=float(draft.amount),
            )
        est_fee = 1.25
        total = float(draft.amount) + est_fee
        return TransactionPreview(draft=draft, network="Sepolia (testnet)", est_fee=est_fee, total=total)

    def send_transaction(self, preview: TransactionPreview) -> SendResult:
        if not self.is_unlocked or self._wallet is None:
            return SendResult(ok=False, error="Vault is locked. Unlock in Settings with your passphrase.")
        ks = self.load_security_settings()
        if ks["killswitch_enabled"]:
            return SendResult(ok=False, error="Kill switch is on. Transaction blocked.")
        d = preview.draft
        debit = float(d.amount)
        assets = self._wallet.get_holdings()
        for a in assets:
            if a.symbol.upper() != d.symbol.upper():
                continue
            if float(a.balance) < debit:
                return SendResult(ok=False, error="Insufficient balance for amount.")
            new_bal = float(a.balance) - debit
            self._wallet.replace_symbol_balance(d.symbol, new_bal, a.kind)
            # Signing would decrypt private key only in-memory here; never persist or log it.
            return SendResult(ok=True, tx_hash="0xSEPOLIA_TESTNET_DEMO_TX")
        return SendResult(ok=False, error=f"Unknown asset symbol: {d.symbol}")

    def reset_vault(self, confirm: bool = False) -> None:
        """
        Permanently deletes the vault and all encrypted data.
        Used when user forgets passphrase.
        """
        if not confirm:
            raise VaultError("Vault reset requires confirmation.")
    
        # Clear in-memory crypto + repos
        self._clear_unlock()
    
        # Close DB connection
        try:
            self._db.close()
        except Exception:
            pass
    
        # Delete DB file
        import os
        if os.path.exists(self._db.path):
            os.remove(self._db.path)
    
        # Recreate fresh database
        self._db = Database(self._db.path)
        self._db.init_schema()

    # Vault is now completely wiped and uninitialized

    # ---- Transaction history helpers (UI can call via hasattr) ----
    def log_transaction_preview(self, preview: TransactionPreview) -> int:
        return self._tx.log_preview(preview)

    def log_transaction_result(self, tx_id: int, result: SendResult) -> None:
        self._tx.update_result(tx_id, result)

    def list_transactions(self, limit: int = 50) -> list[TransactionRecord]:
        return self._tx.list_recent(limit=limit)
