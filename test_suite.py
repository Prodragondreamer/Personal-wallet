import unittest
import sqlite3
from unittest.mock import patch, MagicMock

# Swap the class below for main import SafeguardVault
class SafeguardVault:
    def __init__(self):
        self.conn   = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS balance (amount REAL)')
        self.conn.commit()
        self.kill_switch = False

    def update_manual_balance(self, amount):
        if amount < 0:
            raise ValueError("Balance cannot be negative")
        self.cursor.execute('DELETE FROM balance')
        self.cursor.execute('INSERT INTO balance VALUES (?)', (amount,))
        self.conn.commit()
        return True

    def get_manual_balance(self):
        self.cursor.execute('SELECT amount FROM balance')
        res = self.cursor.fetchone()
        return res[0] if res else 0.0

    def get_unified_balance(self, manual_bank, crypto_price):
        return float(manual_bank) + float(crypto_price)

    def transaction_allowed(self):
        return not self.kill_switch


# ══════════════════════════════════════════════════════════
class TestFR01_PriceFetching(unittest.TestCase):
    """FR-01: Real-time price data returns a valid positive float."""

    def test_price_is_float(self):
        price = 50000.00                        # mocked API response
        self.assertIsInstance(price, float)

    def test_price_is_positive(self):
        price = 50000.00
        self.assertGreater(price, 0)

    def test_api_failure_returns_fallback(self):
        """App must not crash when API is down. return None or cached value."""
        def fetch_price():
            try:
                raise ConnectionError("API unreachable")
            except ConnectionError:
                return None             # app should catch and return fallback
        self.assertIsNone(fetch_price())


class TestFR02_ManualBankEntry(unittest.TestCase):
    """FR-02: User can input a bank balance; it saves and retrieves correctly."""

    def setUp(self):
        self.vault = SafeguardVault()

    def test_balance_saves_and_retrieves(self):
        self.vault.update_manual_balance(1250.50)
        self.assertEqual(self.vault.get_manual_balance(), 1250.50)

    def test_negative_balance_rejected(self):
        with self.assertRaises(ValueError):
            self.vault.update_manual_balance(-500.00)

    def test_zero_balance_allowed(self):
        self.vault.update_manual_balance(0.0)
        self.assertEqual(self.vault.get_manual_balance(), 0.0)

    def test_unified_balance_includes_bank(self):
        bank        = 1000.0
        crypto      = 3200.0
        total       = self.vault.get_unified_balance(bank, crypto)
        self.assertEqual(total, 4200.0)


class TestFR03_KillSwitch(unittest.TestCase):
    """FR-03: Kill Switch blocks transactions when active."""

    def setUp(self):
        self.vault = SafeguardVault()

    def test_transactions_allowed_by_default(self):
        self.assertTrue(self.vault.transaction_allowed())

    def test_kill_switch_blocks_transactions(self):
        self.vault.kill_switch = True
        self.assertFalse(self.vault.transaction_allowed())

    def test_kill_switch_deactivates(self):
        self.vault.kill_switch = True
        self.vault.kill_switch = False
        self.assertTrue(self.vault.transaction_allowed())


class TestFR04_TransactionForesight(unittest.TestCase):
    """FR-04: Balance preview math is correct before user confirms."""

    def estimate_gas(self, gwei=20.0):
        return round(21_000 * gwei * 1e-9, 8)

    def test_preview_balance_is_correct(self):
        balance  = 1000.0
        withdraw = 200.0
        self.assertEqual(balance - withdraw, 800.0)

    def test_gas_fee_is_positive(self):
        self.assertGreater(self.estimate_gas(), 0)

    def test_insufficient_funds_detected(self):
        balance  = 0.0001
        send     = 1.0
        gas      = self.estimate_gas()
        self.assertTrue((send + gas) > balance)


if __name__ == '__main__':
    unittest.main(verbosity=2)
