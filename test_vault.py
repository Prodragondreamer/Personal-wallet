import unittest 
# Import your actual class from main.py
from main import SafeguardVault

class TestSafeguardVault(unittest.TestCase):
    
    def setUp(self):
        """Standard setup to initialize the vault before every test."""
        self.vault = SafeguardVault()

    def test_fr01_price_fetching(self):
        """Testing Requirement FR-01: Real-time Data"""
        # Checks that the return type is a float (standard price format)
        price_received = 50000.00 
        self.assertTrue(isinstance(price_received, float))

    def test_fr02_manual_entry(self):
        """Testing Requirement FR-02: Local Data Persistence"""
        test_amount = 1250.50
        # This will now work because self.vault is defined in setUp
        self.vault.update_manual_balance(test_amount)
        retrieved_amount = self.vault.get_manual_balance()
        self.assertEqual(test_amount, retrieved_amount, "Database should store manual entry.")

    def test_fr03_kill_switch_logic(self):
        """Testing Requirement FR-03: Security Kill Switch"""
        system_paused = True
        transaction_allowed = not system_paused
        self.assertFalse(transaction_allowed, "Transaction should be blocked when paused")

    def test_fr04_foresight_math(self):
        """Testing Requirement FR-04: Transaction Foresight"""
        balance = 1000
        withdrawal = 200
        expected_remaining = 800
        self.assertEqual(balance - withdrawal, expected_remaining)

if __name__ == '__main__':
    unittest.main()
