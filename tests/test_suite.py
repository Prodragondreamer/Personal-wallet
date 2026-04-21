import sys, os, unittest, tempfile
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from walletapp.models import AssetKind, TransactionDraft
from walletapp.services.secure_backend import SecureWalletBackend
from walletapp.exceptions import VaultError

DRAFT = TransactionDraft(AssetKind.CRYPTO, "ETH", 0.1, "0xABCD")
BIG   = TransactionDraft(AssetKind.CRYPTO, "ETH", 99999.0, "0xABCD")


def make_vault():
    v = SecureWalletBackend(tempfile.mktemp(suffix=".db"))
    v.initialize_vault("testpass123")
    return v

def ks_on(v):
    v.save_security_settings(killswitch=True, require_pin=False, biometrics=False)

def ks_off(v):
    v.save_security_settings(killswitch=False, require_pin=False, biometrics=False)


class TestFR01_PriceFetching(unittest.TestCase):
    """FR-01: Portfolio total is a valid positive float."""

    def setUp(self): self.vault = make_vault()

    def test_total_is_positive(self):
        self.assertGreater(self.vault.get_portfolio_total_usd(), 0)

    def test_total_is_float(self):
        self.assertIsInstance(self.vault.get_portfolio_total_usd(), float)

    def test_locked_vault_returns_zero(self):
        self.vault.lock()
        self.assertEqual(self.vault.get_portfolio_total_usd(), 0.0)


class TestFR02_ManualBankEntry(unittest.TestCase):
    """FR-02: Encrypted balances save and retrieve correctly."""

    def setUp(self): self.vault = make_vault()

    def test_symbols_present(self):
        symbols = [a.symbol for a in self.vault.list_assets()]
        self.assertIn("ETH", symbols)
        self.assertIn("AAPL", symbols)

    def test_locked_vault_returns_empty(self):
        self.vault.lock()
        self.assertEqual(self.vault.list_assets(), [])

    def test_all_balances_positive(self):
        for a in self.vault.list_assets():
            self.assertGreater(a.balance, 0)

    def test_asset_count_and_total(self):
        self.assertEqual(len(self.vault.list_assets()), 3)
        self.assertGreater(self.vault.get_portfolio_total_usd(), 0)


class TestFR03_KillSwitch(unittest.TestCase):
    """FR-03: Kill Switch blocks transactions."""

    def setUp(self): self.vault = make_vault()

    def test_off_by_default(self):
        self.assertFalse(self.vault.load_security_settings()["killswitch_enabled"])

    def test_blocks_send(self):
        ks_on(self.vault)
        result = self.vault.send_transaction(self.vault.preview_transaction(DRAFT))
        self.assertFalse(result.ok)
        self.assertIn("Kill switch", result.error)

    def test_preview_shows_blocked(self):
        ks_on(self.vault)
        self.assertIn("blocked", self.vault.preview_transaction(DRAFT).network)

    def test_deactivates(self):
        ks_on(self.vault); ks_off(self.vault)
        self.assertFalse(self.vault.load_security_settings()["killswitch_enabled"])

    def test_locked_vault_blocks_send(self):
        self.vault.lock()
        result = self.vault.send_transaction(self.vault.preview_transaction(DRAFT))
        self.assertFalse(result.ok)


class TestFR04_TransactionForesight(unittest.TestCase):
    """FR-04: Preview fee and total are correct before confirming."""

    def setUp(self):
        self.vault   = make_vault()
        self.preview = self.vault.preview_transaction(DRAFT)

    def test_fee_is_positive(self):
        self.assertGreater(self.preview.est_fee, 0)

    def test_total_equals_amount_plus_fee(self):
        self.assertAlmostEqual(self.preview.total, DRAFT.amount + self.preview.est_fee)

    def test_insufficient_balance_blocked(self):
        result = self.vault.send_transaction(self.vault.preview_transaction(BIG))
        self.assertFalse(result.ok)
        self.assertIn("Insufficient", result.error)

    def test_valid_send_returns_hash(self):
        result = self.vault.send_transaction(self.preview)
        self.assertTrue(result.ok)
        self.assertIsNotNone(result.tx_hash)


class TestSecurity_Vault(unittest.TestCase):
    """NFR: Passphrase encryption; keys never stored in plaintext."""

    def setUp(self): self.vault = make_vault()

    def test_wrong_passphrase_fails(self):
        self.vault.lock()
        self.assertFalse(self.vault.unlock("wrongpassword"))

    def test_correct_passphrase_works(self):
        self.vault.lock()
        self.assertTrue(self.vault.unlock("testpass123"))

    def test_short_passphrase_rejected(self):
        v = SecureWalletBackend(tempfile.mktemp(suffix=".db"))
        with self.assertRaises(VaultError):
            v.initialize_vault("short")

    def test_locked_after_lock_call(self):
        self.vault.lock()
        self.assertFalse(self.vault.is_unlocked)


if __name__ == '__main__':
    unittest.main(verbosity=2)
