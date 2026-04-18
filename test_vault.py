import unittest
from main import SafeguardVault

class TestVaultMVP(unittest.TestCase):
    def setUp(self):
        # Mock setup for CI/CD testing
        self.vault = SafeguardVault("https://sepolia.infura.io/v3/mock", "0x0")

    def test_api_connection(self):
        """Test FR-01: Real-time Price Fetching"""
        price = self.vault.get_market_price("BTC-USD")
        self.assertIsInstance(price, float)
        self.assertGreater(price, 0)

    def test_kill_switch_logic(self):
        """Test FR-03: Kill Switch Initial State"""
        status = self.vault.check_kill_switch_status()
        self.assertEqual(status, "System Active")

if __name__ == "__main__":
    unittest.main()
