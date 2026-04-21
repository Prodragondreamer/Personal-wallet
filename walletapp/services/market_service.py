from __future__ import annotations

import time

from pycoingecko import CoinGeckoAPI
import yfinance as yf

# Maps asset symbols to CoinGecko coin IDs
COIN_MAP: dict[str, str] = {
    "BTC":  "bitcoin",
    "ETH":  "ethereum",
    "USDC": "usd-coin",
    "SOL":  "solana",
    "BNB":  "binancecoin",
    "ADA":  "cardano",
    "DOGE": "dogecoin",
}

# Cache duration in seconds — avoids hammering the API on every screen refresh
_CACHE_TTL = 60


class MarketService:

    def __init__(self) -> None:
        self.cg = CoinGeckoAPI()
        self._cache: dict[str, tuple[float, float]] = {}
        # Last known prices — used as fallback when API is unreachable
        self._last_known: dict[str, float] = {
            "ETH":  3000.00,
            "BTC":  65000.00,
            "USDC": 1.00,
            "SOL":  150.00,
            "AAPL": 190.00,
            "TSLA": 250.00,
            "MSFT": 420.00,
        }

    def _cached(self, key: str) -> float | None:
        """return the cached price if fresh, otherwise None."""
        if key in self._cache:
            price, ts = self._cache[key]
            if time.time() - ts < _CACHE_TTL:
                return price
        return None

    def _store(self, key: str, price: float) -> float:
        """Save to cache/last known then return price"""
        self._cache[key] = (price, time.time())
        self._last_known[key] = price
        return price

    def get_crypto_price(self, symbol: str) -> float:
        """
        get live usd price for crypto symbol, if not possible
        return last available price (API)
        """
        symbol = symbol.upper()
        cached = self._cached(symbol)
        if cached is not None:
            return cached

        coin_id = COIN_MAP.get(symbol, symbol.lower())
        try:
            data = self.cg.get_price(ids=coin_id, vs_currencies="usd")
            price = float(data.get(coin_id, {}).get("usd", 0.0))
            if price > 0:
                return self._store(symbol, price)
        except Exception:
            pass

        # API failed — return last known so dashboard doesn't show $0
        return self._last_known.get(symbol, 0.0)

    def get_stock_price(self, ticker: str) -> float:
        """
        get last usd price for a stock, if not possible
        return lsat available price (API)
        """
        ticker = ticker.upper()
        cached = self._cached(ticker)
        if cached is not None:
            return cached

        try:
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                price = float(data["Close"].iloc[-1])
                if price > 0:
                    return self._store(ticker, price)
        except Exception:
            pass

        return self._last_known.get(ticker, 0.0)

    def get_price(self, symbol: str, kind: str) -> float:
        """
        price lookup for either crypto, stock, or cash symbols
        """
        symbol = symbol.upper()
        if kind == "Cash" or symbol in ("USDC", "USDT", "DAI"):
            return 1.0
        if kind == "Crypto" or symbol in COIN_MAP:
            return self.get_crypto_price(symbol)
        return self.get_stock_price(symbol)
