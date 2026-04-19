# Updated main.py logic for local and cloud interaction
from web3 import Web3
import yfinance as yf

class SafeguardVault:
    def __init__(self, provider_url="https://sepolia.infura.io/v3/YOUR_ID"):
        # Connect to Ethereum Sepolia via Cloud Provider
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.is_connected = self.w3.is_connected()

    def __init__(self):
        # FR-02: Setup local database for manual bank entry
        self.conn = sqlite3.connect(':memory:') # Use memory for testing
        self.cursor = self.conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS balance (amount REAL)')
        self.conn.commit()

    def update_manual_balance(self, amount):
        """Requirement FR-02: User manually inputs bank balance."""
        self.cursor.execute('DELETE FROM balance') # Keep only current balance
        self.cursor.execute('INSERT INTO balance VALUES (?)', (amount,))
        self.conn.commit()
        return True

    def get_manual_balance(self):
        self.cursor.execute('SELECT amount FROM balance')
        result = self.cursor.fetchone()
        return result[0] if result else 0.0

    def get_unified_balance(self, manual_bank, crypto_ticker):
        """Calculates total net worth from local and cloud data."""
        # Fetching real-time cloud data
        crypto_price = yf.Ticker(crypto_ticker).history(period="1d")['Close'].iloc[-1]
        # logic for unified view
        return float(manual_bank) + float(crypto_price)

if __name__ == "__main__":
    app = SafeguardVault()
    print(f"Cloud Connection Successful: {app.is_connected}")
