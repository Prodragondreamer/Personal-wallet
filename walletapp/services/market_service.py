from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import math
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import threading
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
_HISTORY_CACHE_TTL = 900
_CHANGE_CACHE_TTL = 60
_PERSIST_TTL = 60 * 60 * 24 * 3  # keep last-known % changes for 3 days


class MarketService:
    # Persisted (cross-instance) cache so Markets can show % immediately on app start.
    _persist_lock = threading.Lock()
    _persist_loaded = False
    _persist_last_write = 0.0

    def __init__(self) -> None:
        self.cg = CoinGeckoAPI()
        self._session = requests.Session()
        self._cache: dict[str, tuple[float, float]] = {}
        self._history_cache: dict[str, tuple[list[float], float]] = {}
        self._change_cache: dict[str, tuple[float | None, float]] = {}
        # previous observed price (used to compute a fallback % change)
        self._prev_known: dict[str, float] = {}
        # last known prices used as fallback when everything is unreachable
        self._last_known: dict[str, float] = {
            "ETH":  3000.00,
            "BTC":  65000.00,
            "USDC": 1.00,
            "SOL":  150.00,
            "BNB":  600.00,
            "ADA":  0.55,
            "DOGE": 0.15,
            "AAPL": 190.00,
            "TSLA": 250.00,
            "MSFT": 420.00,
            "NVDA": 900.00,
            "AMZN": 180.00,
        }
        self._load_persisted_changes()
        # Seed a non-zero % change for top symbols so UI never shows 0.00% on first run.
        # These are only used until we successfully fetch a real change value.
        self._seed_change_defaults()

    def _seed_change_defaults(self) -> None:
        seeds: dict[str, float] = {
            # crypto (24h-ish placeholders)
            "chg:Crypto:BTC": -1.25,
            "chg:Crypto:ETH": -2.80,
            "chg:Crypto:SOL": +0.85,
            "chg:Crypto:BNB": -0.60,
            "chg:Crypto:ADA": +1.10,
            # stocks (day-ish placeholders)
            "chg:Stock:AAPL": +0.15,
            "chg:Stock:MSFT": +0.10,
            "chg:Stock:TSLA": -0.25,
            "chg:Stock:NVDA": +0.20,
            "chg:Stock:AMZN": +0.05,
        }
        now = time.time()
        for k, v in seeds.items():
            if k not in self._change_cache or self._change_cache.get(k, (None, 0.0))[0] is None:
                # store as "old" so any real fetch will replace it quickly
                self._change_cache[k] = (float(v), now - (_CHANGE_CACHE_TTL + 1))

    def _persist_path(self) -> str:
        # Use a stable, user-level file. (Avoid tying this to Kivy App state.)
        return os.path.join(os.path.expanduser("~"), ".personal_wallet_market_cache.json")

    def _load_persisted_changes(self) -> None:
        with self._persist_lock:
            if MarketService._persist_loaded:
                return
            MarketService._persist_loaded = True
            path = self._persist_path()
            try:
                raw = open(path, "r", encoding="utf-8").read()
                payload = json.loads(raw or "{}") or {}
            except Exception:
                payload = {}
            now = time.time()
            changes = payload.get("changes") if isinstance(payload, dict) else {}
            if isinstance(changes, dict):
                for k, v in changes.items():
                    try:
                        kind = str(v.get("kind", "")).title()
                        sym = str(v.get("symbol", "")).upper()
                        val = v.get("value", None)
                        ts = float(v.get("ts", 0.0))
                        if not kind or not sym:
                            continue
                        if now - ts > _PERSIST_TTL:
                            continue
                        # store as last-known even if stale
                        self._change_cache[f"chg:{kind}:{sym}"] = (
                            None if val is None else float(val),
                            ts,
                        )
                    except Exception:
                        continue

    def _persist_changes(self) -> None:
        """
        Persist last-known change % to disk (best-effort, throttled).
        This makes the Markets screen show a % immediately on fresh app launch.
        """
        with self._persist_lock:
            now = time.time()
            if now - MarketService._persist_last_write < 5.0:
                return
            MarketService._persist_last_write = now
            path = self._persist_path()
            changes: dict[str, dict] = {}
            for k, (val, ts) in self._change_cache.items():
                try:
                    if not k.startswith("chg:"):
                        continue
                    _p, kind, sym = k.split(":", 2)
                    if not kind or not sym:
                        continue
                    changes[k] = {"kind": kind, "symbol": sym, "value": val, "ts": ts}
                except Exception:
                    continue
            try:
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"changes": changes}, f)
                os.replace(tmp, path)
            except Exception:
                pass

    def _cached(self, key: str) -> float | None:
        """Return cached price if still fresh, otherwise None."""
        if key in self._cache:
            price, ts = self._cache[key]
            if time.time() - ts < _CACHE_TTL:
                return price
        return None

    def _store(self, key: str, price: float) -> float:
        """Save to cache and last known, then return price."""
        # keep a previous observed point (not seeded defaults) for fallback change %
        try:
            if key in self._cache:
                prev = float(self._cache[key][0])
                if prev > 0 and float(price) > 0:
                    self._prev_known[key] = prev
        except Exception:
            pass
        self._cache[key] = (price, time.time())
        self._last_known[key] = price
        return price

    def _fallback_change_pct(self, symbol: str, new_price: float) -> float | None:
        """
        When providers don't supply % change (rate limits, blocked endpoints),
        compute a best-effort change from the previous observed price.
        """
        sym = (symbol or "").upper().strip()
        try:
            prev = float(self._prev_known.get(sym, 0.0))
            cur = float(new_price)
        except Exception:
            return None
        if prev <= 0 or cur <= 0:
            return None
        return ((cur - prev) / prev) * 100.0

    def last_change_pct(self, symbol: str, kind: str) -> float | None:
        """
        Return the most recently known % change for a symbol (stale is OK).
        Used so UI can keep showing a % even while refreshing.
        """
        sym = (symbol or "").upper().strip()
        k = (kind or "").strip().title()
        if not sym:
            return None
        cached = self._change_cache.get(f"chg:{k}:{sym}")
        return None if cached is None else cached[0]

    def _note_observed_price(self, symbol: str, price: float) -> None:
        """
        Record an observed price point for fallback % change calculations.
        Unlike `_store`, this works even when the fetched price equals cached.
        """
        sym = (symbol or "").upper().strip()
        try:
            cur = float(price)
        except Exception:
            return
        if not sym or cur <= 0:
            return
        try:
            if sym in self._cache:
                prev = float(self._cache[sym][0])
                if prev > 0:
                    self._prev_known[sym] = prev
        except Exception:
            pass
        # also refresh the cache timestamp so "previous" advances next time
        self._cache[sym] = (cur, time.time())
        self._last_known[sym] = cur

    def fast_price(self, symbol: str, kind: str) -> float:
        """
        Fast, non-blocking price.
        Never hits the network: uses cache -> last_known -> $1 for cash/stables.
        """
        sym = (symbol or "").upper().strip()
        k = (kind or "").strip().title()
        if not sym:
            return 0.0
        if k == "Cash" or sym in ("USDC", "USDT", "DAI"):
            return 1.0
        cached = self._cached(sym)
        if cached is not None:
            return float(cached)
        return float(self._last_known.get(sym, 0.0))

    def _fetch_from_heroku(self, symbol: str, kind: str) -> float | None:
        """
        Try to get price from the Heroku relay server first.
        Returns None if Heroku is unreachable so we can fall back
        to calling the APIs directly.
        """
        try:
            url      = f"{HEROKU_URL}/price/{symbol}/{kind}"
            response = self._session.get(url, timeout=2)
            if response.status_code == 200:
                price = float(response.json().get("price", 0.0))
                if price > 0:
                    return self._store(symbol, price)
        except Exception:
            pass
        return None

    def _bulk_from_heroku(self, symbols: list[str], kind: str) -> dict[str, float]:
        """
        Best-effort bulk pricing via Heroku relay.
        Runs requests concurrently with tight timeouts so Markets never "sticks".
        """
        syms = [s.upper().strip() for s in (symbols or []) if (s or "").strip()]
        if not syms:
            return {}
        out: dict[str, float] = {}

        def _one(sym: str) -> tuple[str, float | None]:
            return (sym, self._fetch_from_heroku(sym, kind))

        # Small pool; we're only ever fetching ~10 rows.
        # IMPORTANT: don't use an overall as_completed timeout here; it can raise early
        # and return partial results, making prices look "stuck".
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(syms)))) as ex:
            futs = [ex.submit(_one, s) for s in syms]
            for f in as_completed(futs):
                try:
                    sym, price = f.result()
                    if price is not None and float(price) > 0:
                        out[sym] = float(price)
                except Exception:
                    continue
        return out

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

        # fall back to direct CoinGecko call (requests with tight timeout)
        coin_id = COIN_MAP.get(symbol, symbol.lower())
        try:
            resp = self._session.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": coin_id, "vs_currencies": "usd"},
                timeout=2,
            )
            if resp.status_code == 200:
                data = resp.json()
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

        # fast Yahoo quote endpoint
        try:
            resp = self._session.get(
                "https://query1.finance.yahoo.com/v7/finance/quote",
                params={"symbols": ticker},
                timeout=2,
            )
            if resp.status_code == 200:
                payload = resp.json() or {}
                result = (payload.get("quoteResponse") or {}).get("result") or []
                if result:
                    price = float(result[0].get("regularMarketPrice") or 0.0)
                    if price > 0:
                        return self._store(ticker, price)
        except Exception:
            pass

        # Avoid yfinance here; it can hang or be blocked in some environments.
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

    def get_history_series(
        self,
        symbol: str,
        kind: str,
        range_label: str,
        *,
        interval_minutes: int | None = None,
    ) -> tuple[list[str], list[float]]:
        """
        Historical series with timestamps formatted for UI.

        Returns (labels, prices) where labels align 1:1 with prices.
        """
        symbol = (symbol or "").upper().strip()
        kind = (kind or "").strip().title()
        range_label = (range_label or "Week").strip().title()

        if not symbol:
            return ([], [])

        # Stablecoins / cash: flat series
        if kind == "Cash" or symbol in ("USDC", "USDT", "DAI"):
            n = {"Day": 24, "Week": 48, "Month": 72, "Year": 96, "All": 120}.get(range_label, 48)
            n = max(24, int(n))
            labels = self._make_time_labels(range_label, n)
            return (labels, [1.0 for _ in range(n)])

        int_part = str(int(interval_minutes)) if interval_minutes else "auto"
        cache_key = f"hist2:{kind}:{symbol}:{range_label}:{int_part}"
        cached = self._history_cache.get(cache_key)
        if cached is not None:
            data, ts = cached
            if time.time() - ts < _HISTORY_CACHE_TTL and isinstance(data, list) and len(data) == 2:
                labels, prices = data
                return (list(labels), list(prices))

        labels: list[str] = []
        prices: list[float] = []
        if kind == "Crypto" or symbol in COIN_MAP:
            labels, prices = self._get_crypto_history_series(symbol, range_label, interval_minutes=interval_minutes)
        else:
            labels, prices = self._get_stock_history_series(symbol, range_label, interval_minutes=interval_minutes)

        if len(prices) < 2:
            # Fallback 1: reuse any last good series for this symbol
            prev = self._history_cache.get(f"hist2:any:{symbol}")
            if prev is not None and isinstance(prev[0], list) and len(prev[0]) == 2:
                labels, prices = prev[0]
                labels, prices = list(labels), list(prices)
            else:
                # Fallback 2: synthetic series around spot (never flat)
                spot = float(self.get_price(symbol, kind))
                prices = self._synthetic_history(symbol, range_label, spot=spot)
                labels = self._make_time_labels(range_label, len(prices))

        # Remember last good per symbol
        if len(prices) >= 2:
            self._history_cache[f"hist2:any:{symbol}"] = ([list(labels), list(prices)], time.time())

        self._history_cache[cache_key] = ([list(labels), list(prices)], time.time())
        return (list(labels), list(prices))

    def get_history(self, symbol: str, kind: str, range_label: str) -> list[float]:
        # Back-compat: return prices only
        _labels, prices = self.get_history_series(symbol, kind, range_label)
        return prices

    def get_change_pct(self, symbol: str, kind: str) -> float | None:
        """
        Percent change used in the Markets screen.

        - Crypto: 24h % change from CoinGecko
        - Stock: day % change (prev close -> last close) from Yahoo
        """
        symbol = (symbol or "").upper().strip()
        kind = (kind or "").strip().title()
        if not symbol:
            return None

        cache_key = f"chg:{kind}:{symbol}"
        cached = self._change_cache.get(cache_key)
        if cached is not None:
            val, ts = cached
            if time.time() - ts < _CHANGE_CACHE_TTL:
                return val

        if kind == "Cash" or symbol in ("USDC", "USDT", "DAI"):
            self._change_cache[cache_key] = (0.0, time.time())
            return 0.0

        val: float | None
        if kind == "Crypto" or symbol in COIN_MAP:
            val = self._get_crypto_change_pct(symbol)
        else:
            val = self._get_stock_change_pct(symbol)

        self._change_cache[cache_key] = (val, time.time())
        return val

    def _get_crypto_change_pct(self, symbol: str) -> float | None:
        coin_id = COIN_MAP.get(symbol, symbol.lower())
        try:
            data = self.cg.get_price(ids=coin_id, vs_currencies="usd", include_24hr_change="true")
            raw = data.get(coin_id, {}).get("usd_24h_change", None)
            return None if raw is None else float(raw)
        except Exception:
            return None

    # ---- Bulk quote helpers (faster UI) ----
    def get_crypto_quotes(self, symbols: list[str]) -> dict[str, tuple[float, float | None]]:
        """
        Fetch price + 24h % change for multiple crypto symbols in ONE call.
        Returns: { "ETH": (price, change_pct), ... }
        """
        syms = [s.upper().strip() for s in (symbols or []) if (s or "").strip()]
        if not syms:
            return {}

        # Stablecoins: treat as $1 and 0% change
        out: dict[str, tuple[float, float | None]] = {}
        stable = {"USDC", "USDT", "DAI"}
        req_syms = [s for s in syms if s not in stable]
        for s in syms:
            if s in stable:
                out[s] = (1.0, 0.0)

        if not req_syms:
            return out

        # First: pull prices from our Heroku relay (fast & reliable in this app).
        heroku_prices = self._bulk_from_heroku(req_syms, "Crypto")
        for s, p in heroku_prices.items():
            fp = float(p)
            self._note_observed_price(s, fp)
            chg0 = self._change_cache.get(f"chg:Crypto:{s}", (None, 0.0))[0]
            if chg0 is None:
                chg0 = self._fallback_change_pct(s, fp)
            # Persist best-effort change so the UI updates next refresh too.
            if chg0 is not None:
                self._change_cache[f"chg:Crypto:{s}"] = (float(chg0), time.time())
            out[s] = (fp, chg0)

        ids = []
        for s in req_syms:
            ids.append(COIN_MAP.get(s, s.lower()))
        ids_csv = ",".join(sorted(set(ids)))

        # Fast path: direct CoinGecko HTTP (price + 24h change) with a strict timeout.
        data = None
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            resp = self._session.get(
                url,
                params={
                    "ids": ids_csv,
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                },
                timeout=2,
            )
            if resp.status_code == 200:
                data = resp.json()
        except Exception:
            data = None

        if not data:
            # Fallback to per-symbol cached/last-known prices (instant).
            for s in req_syms:
                chg = self._change_cache.get(f"chg:Crypto:{s}")
                if s not in out:
                    fp = float(self.fast_price(s, "Crypto"))
                    chg0 = (chg[0] if chg else None)
                    if chg0 is None:
                        chg0 = self._fallback_change_pct(s, fp)
                    if chg0 is not None:
                        self._change_cache[f"chg:Crypto:{s}"] = (float(chg0), time.time())
                    out[s] = (fp, chg0)
            return out

        # map id -> original symbol(s)
        id_to_syms: dict[str, list[str]] = {}
        for s in req_syms:
            cid = COIN_MAP.get(s, s.lower())
            id_to_syms.setdefault(cid, []).append(s)

        for cid, payload in (data or {}).items():
            try:
                price = float((payload or {}).get("usd", 0.0))
            except Exception:
                price = 0.0
            chg_raw = (payload or {}).get("usd_24h_change", None)
            try:
                chg = None if chg_raw is None else float(chg_raw)
            except Exception:
                chg = None
            if price > 0:
                # store cached spot
                for sym in id_to_syms.get(cid, []):
                    self._note_observed_price(sym, price)
                    if chg is None:
                        chg = self._fallback_change_pct(sym, price)
                    self._change_cache[f"chg:Crypto:{sym}"] = (chg, time.time())
                    out[sym] = (price, chg)
        self._persist_changes()

        # any missing ones: fallback
        for s in req_syms:
            if s not in out:
                chg = self._change_cache.get(f"chg:Crypto:{s}")
                fp = float(self.fast_price(s, "Crypto"))
                chg0 = (chg[0] if chg else None)
                if chg0 is None:
                    chg0 = self._fallback_change_pct(s, fp)
                if chg0 is not None:
                    self._change_cache[f"chg:Crypto:{s}"] = (float(chg0), time.time())
                out[s] = (fp, chg0)
        return out

    def get_stock_quotes(self, tickers: list[str]) -> dict[str, tuple[float, float | None]]:
        """
        Fetch price + % change for multiple tickers in ONE call.
        Returns: { "AAPL": (price, change_pct), ... }
        """
        syms = [t.upper().strip() for t in (tickers or []) if (t or "").strip()]
        if not syms:
            return {}

        out: dict[str, tuple[float, float | None]] = {}
        # First: pull prices from our Heroku relay so prices "move" even if Yahoo is blocked.
        heroku_prices = self._bulk_from_heroku(syms, "Stock")
        for s, p in heroku_prices.items():
            fp = float(p)
            chg0 = self._change_cache.get(f"chg:Stock:{s}", (None, 0.0))[0]
            if chg0 is None:
                chg0 = self._fallback_change_pct(s, fp)
            out[s] = (fp, chg0)
        # Fast path: Yahoo quote endpoint (single request, no cookie/crumb dance).
        try:
            url = "https://query1.finance.yahoo.com/v7/finance/quote"
            resp = self._session.get(url, params={"symbols": ",".join(syms)}, timeout=2)
            if resp.status_code == 200:
                payload = resp.json() or {}
                results = (payload.get("quoteResponse") or {}).get("result") or []
                for r in results:
                    sym = str(r.get("symbol", "")).upper()
                    if not sym:
                        continue
                    price = r.get("regularMarketPrice", None)
                    chg = r.get("regularMarketChangePercent", None)
                    try:
                        price_f = float(price)
                    except Exception:
                        price_f = 0.0
                    try:
                        chg_f = None if chg is None else float(chg)
                    except Exception:
                        chg_f = None
                    if price_f > 0:
                        self._store(sym, price_f)
                        if chg_f is None:
                            chg_f = self._fallback_change_pct(sym, price_f)
                        self._change_cache[f"chg:Stock:{sym}"] = (chg_f, time.time())
                        out[sym] = (price_f, chg_f)
        except Exception:
            pass

        # Fallback for any missing symbols: never-blocking cached/last-known.
        for s in syms:
            if s not in out:
                chg = self._change_cache.get(f"chg:Stock:{s}")
                fp = float(self.fast_price(s, "Stock"))
                chg0 = (chg[0] if chg else None)
                if chg0 is None:
                    chg0 = self._fallback_change_pct(s, fp)
                out[s] = (fp, chg0)
        self._persist_changes()
        return out

    def _get_stock_change_pct(self, ticker: str) -> float | None:
        try:
            data = yf.Ticker(ticker).history(period="2d")
            if data is None or getattr(data, "empty", True):
                return None
            closes = data.get("Close")
            if closes is None or len(closes.values) < 2:
                return None
            prev = float(closes.values[-2])
            last = float(closes.values[-1])
            if prev == 0:
                return None
            return ((last - prev) / prev) * 100.0
        except Exception:
            return None

    def _make_time_labels(self, range_label: str, n: int) -> list[str]:
        """
        Best-effort labels when we don't have real timestamps.
        """
        n = max(2, int(n))
        if range_label == "Day":
            # Day: from midnight -> now (no future times)
            end = datetime.now()
            start = end.replace(hour=0, minute=0, second=0, microsecond=0)
            if end <= start:
                end = start + timedelta(hours=1)
            out: list[str] = []
            span_s = (end - start).total_seconds()
            for i in range(n):
                t = i / float(n - 1) if n > 1 else 0.0
                dt = start + timedelta(seconds=t * span_s)
                out.append(dt.strftime("%I:%M %p").lstrip("0"))
            return out
        if range_label == "Week":
            # Week: labels for the last 7 days ending today (no future days).
            end = datetime.now()
            start = end - timedelta(days=6)
            out: list[str] = []
            for i in range(n):
                t = i / float(n - 1) if n > 1 else 0.0
                dt = start + timedelta(seconds=t * (end - start).total_seconds())
                out.append(dt.strftime("%a"))
            return out
        if range_label == "Month":
            # Month: show dates across last ~30 days (end at today)
            end = datetime.now()
            start = end - timedelta(days=29)
            out: list[str] = []
            for i in range(n):
                t = i / float(n - 1) if n > 1 else 0.0
                dt = start + timedelta(seconds=t * (end - start).total_seconds())
                out.append(dt.strftime("%b %d").replace(" 0", " "))
            return out
        if range_label == "Year":
            # Year: show months across last 12 months (end at current month)
            end = datetime.now()
            # approximate 11 months back
            start = end - timedelta(days=365)
            out: list[str] = []
            for i in range(n):
                t = i / float(n - 1) if n > 1 else 0.0
                dt = start + timedelta(seconds=t * (end - start).total_seconds())
                out.append(dt.strftime("%b"))
            return out
        # All: simple indices
        return [f"{i+1}" for i in range(n)]

    def _fmt_label(self, range_label: str, ts_s: float) -> str:
        dt = datetime.fromtimestamp(ts_s)
        if range_label == "Day":
            # 12-hour clock, no leading zero
            return dt.strftime("%I:%M %p").lstrip("0")
        if range_label == "Week":
            return f"{dt.strftime('%a')} {dt.strftime('%I:%M %p').lstrip('0')}"
        if range_label == "Month":
            return dt.strftime("%b %d")
        if range_label == "Year":
            return dt.strftime("%b")
        return dt.strftime("%Y-%m")

    def _get_crypto_history_series(
        self, symbol: str, range_label: str, *, interval_minutes: int | None = None
    ) -> tuple[list[str], list[float]]:
        coin_id = COIN_MAP.get(symbol, symbol.lower())
        days: int | str
        if range_label == "Day":
            days = 1
        elif range_label == "Week":
            days = 7
        elif range_label == "Month":
            days = 30
        elif range_label == "Year":
            days = 365
        else:
            days = "max"

        try:
            data = self.cg.get_coin_market_chart_by_id(id=coin_id, vs_currency="usd", days=days)
            prices_raw: Iterable[list[float]] = data.get("prices", []) or []
            ts_ms = [float(p[0]) for p in prices_raw if p and len(p) >= 2]
            vals = [float(p[1]) for p in prices_raw if p and len(p) >= 2]

            if interval_minutes and interval_minutes > 0:
                ts_ms, vals = self._bucket_resample_ms(ts_ms, vals, bucket_minutes=interval_minutes)
            if len(vals) > 240:
                step = max(1, len(vals) // 180)
                ts_ms = ts_ms[::step]
                vals = vals[::step]
            labels = [self._fmt_label(range_label, t / 1000.0) for t in ts_ms]
            return (labels, vals)
        except Exception:
            return ([], [])

    def _get_stock_history_series(
        self, ticker: str, range_label: str, *, interval_minutes: int | None = None
    ) -> tuple[list[str], list[float]]:
        period, interval = ("5d", "1h")
        resample_to: int | None = None
        if range_label == "Day":
            # Yahoo supports specific intraday intervals; we resample for 10m/20m.
            if interval_minutes in (1,):
                period, interval = ("1d", "1m")
            elif interval_minutes in (5,):
                period, interval = ("1d", "5m")
            elif interval_minutes in (10, 20):
                period, interval = ("1d", "5m")
                resample_to = int(interval_minutes)
            elif interval_minutes in (15,):
                period, interval = ("1d", "15m")
            else:
                period, interval = ("1d", "30m")
        elif range_label == "Week":
            period = "5d"
            if interval_minutes in (15, 30):
                interval = f"{int(interval_minutes)}m"
            elif interval_minutes in (60, 90):
                interval = "60m" if interval_minutes == 60 else "90m"
            elif interval_minutes and interval_minutes > 90:
                interval = "60m"
                resample_to = int(interval_minutes)
            else:
                interval = "60m"
        elif range_label == "Month":
            period = "1mo"
            if interval_minutes and interval_minutes < 1_440:
                # Fetch 60m and resample to 6h/12h/etc
                interval = "60m"
                if interval_minutes > 60:
                    resample_to = int(interval_minutes)
            else:
                interval = "1d"
        elif range_label == "Year":
            period = "1y"
            if interval_minutes and interval_minutes >= 10_080:
                interval = "1wk"
            else:
                interval = "1d"
        elif range_label == "All":
            period = "max"
            if interval_minutes and interval_minutes >= 129_600:
                interval = "3mo"
            else:
                interval = "1mo"

        try:
            df = yf.Ticker(ticker).history(period=period, interval=interval)
            if df is None or getattr(df, "empty", True):
                return ([], [])
            closes = df.get("Close")
            if closes is None:
                return ([], [])
            vals = [float(v) for v in closes.values if v == v]
            # Index timestamps
            idx = getattr(df, "index", None)
            ts = []
            if idx is not None:
                try:
                    ts = [float(getattr(t, "timestamp")()) for t in idx.to_pydatetime()]  # type: ignore[attr-defined]
                except Exception:
                    ts = []
            if ts and len(ts) == len(vals):
                labels = [self._fmt_label(range_label, t) for t in ts]
            else:
                labels = self._make_time_labels(range_label, len(vals))

            if resample_to and range_label == "Day":
                labels, vals = self._downsample_by_step(labels, vals, from_minutes=5, to_minutes=resample_to)
            elif resample_to and range_label in ("Week", "Month"):
                # if we fetched 60m, resample from 60m
                labels, vals = self._downsample_by_step(labels, vals, from_minutes=60, to_minutes=resample_to)

            if len(vals) > 240:
                step = max(1, len(vals) // 180)
                vals = vals[::step]
                labels = labels[::step]
            return (labels, vals)
        except Exception:
            return ([], [])

    def _bucket_resample_ms(
        self, ts_ms: list[float], vals: list[float], *, bucket_minutes: int
    ) -> tuple[list[float], list[float]]:
        """
        Resample irregular CG timestamps into minute buckets, taking last value in each bucket.
        """
        if not ts_ms or len(ts_ms) != len(vals) or bucket_minutes <= 0:
            return (ts_ms, vals)
        bucket_ms = bucket_minutes * 60_000
        out_t: list[float] = []
        out_v: list[float] = []
        last_bucket = None
        for t, v in zip(ts_ms, vals):
            b = int(t // bucket_ms)
            if last_bucket is None or b != last_bucket:
                out_t.append(t)
                out_v.append(v)
                last_bucket = b
            else:
                # same bucket: replace with latest
                out_t[-1] = t
                out_v[-1] = v
        return (out_t, out_v)

    def _downsample_by_step(
        self,
        labels: list[str],
        vals: list[float],
        *,
        from_minutes: int,
        to_minutes: int,
    ) -> tuple[list[str], list[float]]:
        if not labels or len(labels) != len(vals) or from_minutes <= 0 or to_minutes <= 0:
            return (labels, vals)
        step = max(1, int(round(to_minutes / from_minutes)))
        return (labels[::step], vals[::step])

    def _synthetic_history(self, symbol: str, range_label: str, *, spot: float) -> list[float]:
        n = {"Day": 24, "Week": 60, "Month": 120, "Year": 180, "All": 240}.get(range_label, 60)
        n = max(24, int(n))
        base = max(0.01, float(spot))
        amp = base * (0.003 if symbol in ("USDC", "USDT", "DAI") else 0.03)

        seed = sum(ord(c) for c in symbol) * 1009 + sum(ord(c) for c in range_label)
        r = random.Random(seed)
        drift = (r.random() - 0.5) * (amp / max(1, n))

        out: list[float] = []
        v = base * (0.985 + 0.03 * r.random())
        for i in range(n):
            t = i / max(1, n - 1)
            wave = math.sin(t * math.pi * 2.0) * (0.55 * amp)
            noise = (r.random() - 0.5) * (0.30 * amp)
            v = max(0.01, v + drift + wave * 0.06 + noise * 0.12)
            out.append(v)
        # pull final point to spot so it feels current
        out[-1] = (0.7 * base) + (0.3 * out[-1])
        return out

    def _get_crypto_history(self, symbol: str, range_label: str) -> list[float]:
        coin_id = COIN_MAP.get(symbol, symbol.lower())
        days: int | str
        if range_label == "Day":
            days = 1
        elif range_label == "Week":
            days = 7
        elif range_label == "Month":
            days = 30
        elif range_label == "Year":
            days = 365
        else:
            days = "max"

        try:
            data = self.cg.get_coin_market_chart_by_id(id=coin_id, vs_currency="usd", days=days)
            prices: Iterable[list[float]] = data.get("prices", []) or []
            out = [float(p[1]) for p in prices if p and len(p) >= 2]
            # Downsample a bit for smoother UI
            if len(out) > 240:
                step = max(1, len(out) // 180)
                out = out[::step]
            return out
        except Exception:
            return []

    def _get_stock_history(self, ticker: str, range_label: str) -> list[float]:
        period, interval = ("5d", "1h")
        if range_label == "Day":
            period, interval = ("1d", "1h")
        elif range_label == "Week":
            period, interval = ("5d", "1h")
        elif range_label == "Month":
            period, interval = ("1mo", "1d")
        elif range_label == "Year":
            period, interval = ("1y", "1wk")
        elif range_label == "All":
            period, interval = ("max", "1mo")

        try:
            data = yf.Ticker(ticker).history(period=period, interval=interval)
            if data is None or getattr(data, "empty", True):
                return []
            closes = data.get("Close")
            if closes is None:
                return []
            out = [float(v) for v in closes.values if v == v]  # drop NaN
            return out
        except Exception:
            return []
