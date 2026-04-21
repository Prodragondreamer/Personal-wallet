from __future__ import annotations

import time
import requests

from pycoingecko import CoinGeckoAPI
import yfinance as yf

HEROKU_URL = "https://personal-wallet-api-99d590253849.herokuapp.com"

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

# cache duration in seconds avoids hammering the API on every screen refresh
_CACHE_TTL = 60


class MarketService:

    def __init__(self) -> None:
        self.cg = CoinGeckoAPI()
        self._cache: dict[str, tuple[float, float]] = {}
        # last known prices used as fallback when everything is unreachable
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
        """Return cached price if still fresh, otherwise None."""
        if key in self._cache:
            price, ts = self._cache[key]
            if time.time() - ts < _CACHE_TTL:
                return price
        return None

    def _store(self, key: str, price: float) -> float:
        """Save to cache and last known, then return price."""
        self._cache[key] = (price, time.time())
        self._last_known[key] = price
        return price

    def _fetch_from_heroku(self, symbol: str, kind: str) -> float | None:
        """
        Try to get price from the Heroku relay server first.
        Returns None if Heroku is unreachable so we can fall back
        to calling the APIs directly.
        """
        try:
            url      = f"{HEROKU_URL}/price/{symbol}/{kind}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                price = float(response.json().get("price", 0.0))
                if price > 0:
                    return self._store(symbol, price)
        except Exception:
            pass
        return None

    def get_crypto_price(self, symbol: str) -> float:
        """
        Get live USD price for a crypto symbol (e.g. 'ETH').
        Tries Heroku first, falls back to direct CoinGecko call,
        then falls back to last known price.
        """
        symbol = symbol.upper()

        # checks cache
        cached = self._cached(symbol)
        if cached is not None:
            return cached

        # tries Heroku relay
        heroku_price = self._fetch_from_heroku(symbol, "Crypto")
        if heroku_price is not None:
            return heroku_price

        # fall back to direct CoinGecko call
        coin_id = COIN_MAP.get(symbol, symbol.lower())
        try:
            data  = self.cg.get_price(ids=coin_id, vs_currencies="usd")
            price = float(data.get(coin_id, {}).get("usd", 0.0))
            if price > 0:
                return self._store(symbol, price)
        except Exception:
            pass

        # last known price
        return self._last_known.get(symbol, 0.0)

    def get_stock_price(self, ticker: str) -> float:
        """
        Get live USD price for a stock ticker (e.g. 'AAPL').
        Tries Heroku first, falls back to direct Yahoo Finance call,
        then falls back to last known price.
        """
        ticker = ticker.upper()

        cached = self._cached(ticker)
        if cached is not None:
            return cached

        heroku_price = self._fetch_from_heroku(ticker, "Stock")
        if heroku_price is not None:
            return heroku_price

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
        Unified price lookup — pass the asset symbol and kind string.
        kind: 'Crypto' | 'Stock' | 'Cash'
        """
        symbol = symbol.upper()
        if kind == "Cash" or symbol in ("USDC", "USDT", "DAI"):
            return 1.0
        if kind == "Crypto" or symbol in COIN_MAP:
            return self.get_crypto_price(symbol)
        return self.get_stock_price(symbol)
