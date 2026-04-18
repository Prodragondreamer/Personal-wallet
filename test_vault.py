import unittest
from main import SafeguardVault

class TestSafeguardVault(unittest.TestCase):
    def setUp(self):
        # Use a mock or local provider for testing
        self.vault = SafeguardVault("https://rpc.ankr.com/eth_sepolia", "0x0000000000000000000000000000000000000000")

    def test_market_api(self):
        """Test Case for FR-01: Real-time Price Fetching"""
        price = self.vault.get_market_price("ETH-USD")
        self.assertGreater(price, 0, "Price fetching failed")

    def test_system_initialization(self):
        """Test Case for FR-03: Kill Switch Connectivity"""
        status = self.vault.check_system_status()
        self.assertIn(status, ["Operational", "Contract Not Found"])

if __name__ == "__main__":
    unittest.main()
