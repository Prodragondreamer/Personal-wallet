import sqlite3
from web3 import Web3
from pycoingecko import CoinGeckoAPI
import yfinance as yf


class SafeguardVault:
    def __init__(self, provider_url="https://sepolia.infura.io/v3/YOUR_ID"):
        # -------------------------
        # Blockchain (Web3)
        # -------------------------
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.is_connected = self.w3.is_connected()

        # -------------------------
        # Local Database (SQLite)
        # -------------------------
        self.conn = sqlite3.connect(':memory:')  # change to file later if needed
        self.cursor = self.conn.cursor()

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS bank_balance (
                amount REAL
            )
        """)

        self.conn.commit()

        # -------------------------
        # API Clients
        # -------------------------
        self.cg = CoinGeckoAPI()

        # -------------------------
        # In-memory assets
        # -------------------------
        self.stocks = []   # [{ticker, shares, price}]
        self.cryptos = []  # [{id, quantity, price}]

    # =========================
    # BANK (FR-02)
    # =========================
    def update_manual_balance(self, amount: float):
        if amount < 0:
            raise ValueError("Balance cannot be negative")

        self.cursor.execute("DELETE FROM bank_balance")
        self.cursor.execute("INSERT INTO bank_balance VALUES (?)", (amount,))
        self.conn.commit()

    def get_manual_balance(self) -> float:
        self.cursor.execute("SELECT amount FROM bank_balance")
        result = self.cursor.fetchone()
        return result[0] if result else 0.0

    # =========================
    # STOCKS (Yahoo Finance)
    # =========================
    def add_stock(self, ticker: str, shares: float):
        if shares <= 0:
            raise ValueError("Shares must be > 0")

        self.stocks.append({
            "ticker": ticker.upper(),
            "shares": shares,
            "price": 0.0
        })

    def get_stock_price(self, ticker: str) -> float:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")

        if data.empty:
            raise ValueError(f"Invalid stock ticker: {ticker}")

        return float(data["Close"].iloc[-1])

    def update_stock_prices(self):
        for stock in self.stocks:
            stock["price"] = self.get_stock_price(stock["ticker"])

    # =========================
    # CRYPTO (CoinGecko)
    # =========================
    def add_crypto(self, coin_id: str, quantity: float):
        if quantity <= 0:
            raise ValueError("Quantity must be > 0")

        self.cryptos.append({
            "id": coin_id.lower(),
            "quantity": quantity,
            "price": 0.0
        })

    def get_crypto_price(self, coin_id: str) -> float:
        data = self.cg.get_price(ids=coin_id, vs_currencies="usd")

        if coin_id not in data:
            raise ValueError(f"Invalid crypto id: {coin_id}")

        return float(data[coin_id]["usd"])

    def update_crypto_prices(self):
        for crypto in self.cryptos:
            crypto["price"] = self.get_crypto_price(crypto["id"])

    # =========================
    # PORTFOLIO CALCULATION
    # =========================
    def calculate_totals(self):
        bank = self.get_manual_balance()

        stock_total = sum(s["shares"] * s["price"] for s in self.stocks)
        crypto_total = sum(c["quantity"] * c["price"] for c in self.cryptos)

        grand_total = bank + stock_total + crypto_total

        return {
            "bank": round(bank, 2),
            "stocks": round(stock_total, 2),
            "crypto": round(crypto_total, 2),
            "total": round(grand_total, 2)
        }

    def refresh_all_data(self):
        self.update_stock_prices()
        self.update_crypto_prices()
        return self.calculate_totals()

    # =========================
    # TRANSACTION FORESIGHT
    # =========================
    def preview_transaction(self, coin_id: str, amount: float):
        if amount <= 0:
            raise ValueError("Amount must be > 0")

        price = self.get_crypto_price(coin_id)

        asset_cost = amount * price
        gas_fee = 10  # simple estimate
        total_cost = asset_cost + gas_fee

        balance = self.get_manual_balance()

        return {
            "asset": coin_id,
            "amount": amount,
            "price": round(price, 2),
            "asset_cost": round(asset_cost, 2),
            "gas_fee": gas_fee,
            "total_cost": round(total_cost, 2),
            "balance": round(balance, 2),
            "safe": balance >= total_cost
        }

    # =========================
    # DEBUG / TEST
    # =========================
    def debug_summary(self):
        return {
            "stocks": self.stocks,
            "cryptos": self.cryptos,
            "bank": self.get_manual_balance()
        }
