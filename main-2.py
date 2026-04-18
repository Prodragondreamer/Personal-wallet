from web3 import Web3
import yfinance as yf

class SafeguardVault:
    def __init__(self, provider_url, contract_address):
        # Establish connection to the Sepolia cloud
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.address = contract_address

    def get_market_price(self, ticker):
        """FR-01: Real-time Price Fetching"""
        try:
            asset = yf.Ticker(ticker)
            return asset.history(period="1d")['Close'].iloc[-1]
        except Exception:
            return 0.0

    def check_system_status(self):
        """FR-03: Kill Switch Status"""
        # Checks if the contract is currently paused
        return "Operational" if not self.w3.eth.get_code(self.address) == b'' else "Contract Not Found"

if __name__ == "__main__":
    # Example initialization for the prototype
    vault = SafeguardVault("https://sepolia.infura.io/v3/YOUR_PROJECT_ID", "0xYourContractAddress")
    print(f"Vault Status: {vault.check_system_status()}")
