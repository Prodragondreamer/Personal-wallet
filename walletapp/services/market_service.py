from pycoingecko import CoinGeckoAPI
import yfinance as yf


class MarketService:
    def __init__(self):
        self.cg = CoinGeckoAPI()

    def get_stock_price(self, ticker: str) -> float:
        stock = yf.Ticker(ticker)
        data = stock.history(period="1d")

        if data.empty:
            return 0.0

        return float(data["Close"].iloc[-1])

    def get_crypto_price(self, coin_id: str) -> float:
        data = self.cg.get_price(ids=coin_id, vs_currencies="usd")
        return data.get(coin_id, {}).get("usd", 0.0)
