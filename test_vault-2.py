import unittest
from main import SafeguardVault

class TestVaultAutomation(unittest.TestCase):
    def setUp(self):
        # Using a dummy address for CI testing
        self.vault = SafeguardVault("https://sepolia.infura.io/v3/mock", "0x000")

    def test_api_integration(self):
        """Test Case FR-01: Real-time Price Fetching"""
        price = self.vault.get_market_price("BTC-USD")
        self.assertIsInstance(price, float)
        self.assertGreater(price, 0)

    def test_kill_switch_logic(self):
        """Test Case FR-03: Kill Switch Initial State"""
        status = self.vault.check_kill_switch_status()
        self.assertEqual(status, "System Active")
