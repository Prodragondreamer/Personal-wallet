from web3 import Web3
import yfinance as yf

# Cloud/Blockchain Bridge [cite: 24, 171]
class SafeguardVault:
    def __init__(self, provider_url, contract_address):
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.address = contract_address

    def get_market_price(self, ticker):
        # API Integration: Functional Requirement FR-01 [cite: 23, 34]
        data = yf.Ticker(ticker)
        return data.history(period="1d")['Close'].iloc[-1]

    def check_kill_switch_status(self):
        # Security Requirement FR-03 
        # In a real app, this calls the contract.paused() function
        return "System Active" 

if __name__ == "__main__":
    vault = SafeguardVault("https://sepolia.infura.io/v3/YOUR_ID", "0xAddress")
    print(f"Status: {vault.check_kill_switch_status()}")
