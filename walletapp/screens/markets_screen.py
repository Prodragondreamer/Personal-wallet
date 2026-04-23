from __future__ import annotations

import threading

from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, StringProperty

from walletapp.screens.base import WalletScreen
from walletapp.services.market_service import MarketService


class MarketsScreen(WalletScreen):
    is_fetching = BooleanProperty(False)
    status_text = StringProperty("")
    crypto_rows = ListProperty([])  # list[dict]
    stock_rows = ListProperty([])  # list[dict]

    _top_cryptos = ["BTC", "ETH", "SOL", "BNB", "ADA"]
    _top_stocks = ["AAPL", "MSFT", "TSLA", "NVDA", "AMZN"]
    _refresh_ev = None

    def on_pre_enter(self, *args) -> None:
        # Auto-refresh every 15s while on this screen.
        if self._refresh_ev is None:
            self._refresh_ev = Clock.schedule_interval(lambda _dt: self.refresh(), 15.0)
        self.refresh()

    def on_leave(self, *args) -> None:
        # Stop timer when leaving Markets.
        if self._refresh_ev is not None:
            try:
                self._refresh_ev.cancel()
            except Exception:
                pass
            self._refresh_ev = None

    def refresh(self) -> None:
        if self.is_fetching:
            return
        self.is_fetching = True
        self.status_text = "Updating prices…"
        # Only show placeholders the very first time (keep last prices visible on refresh).
        if not self.crypto_rows:
            self.crypto_rows = [self._placeholder(sym) for sym in self._top_cryptos]
        if not self.stock_rows:
            self.stock_rows = [self._placeholder(sym) for sym in self._top_stocks]
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self) -> None:
        market = MarketService()
        try:
            cq = market.get_crypto_quotes(self._top_cryptos)
            sq = market.get_stock_quotes(self._top_stocks)

            crypto = []
            for sym in self._top_cryptos:
                price, chg = cq.get(sym, (market.get_price(sym, "Crypto"), market.get_change_pct(sym, "Crypto")))
                crypto.append(self._row(sym, float(price), chg))

            stocks = []
            for sym in self._top_stocks:
                price, chg = sq.get(sym, (market.get_price(sym, "Stock"), market.get_change_pct(sym, "Stock")))
                stocks.append(self._row(sym, float(price), chg))

            status = "Live prices (CoinGecko + Yahoo Finance)."
        except Exception as e:
            crypto = []
            stocks = []
            status = f"Error fetching markets: {e}"

        Clock.schedule_once(lambda _dt: self._apply(crypto, stocks, status))

    def _apply(self, crypto: list[dict], stocks: list[dict], status: str) -> None:
        self.crypto_rows = crypto
        self.stock_rows = stocks
        self.status_text = status
        self.is_fetching = False

    def _row(self, symbol: str, price: float, change_pct: float | None) -> dict:
        change_str = "—" if change_pct is None else f"{change_pct:+.2f}%"
        is_pos = (change_pct or 0.0) >= 0.0
        color = (0.60, 0.90, 0.60, 1) if is_pos else (0.95, 0.35, 0.35, 1)
        return {
            "symbol": symbol,
            "price": f"${price:,.2f}",
            "change": change_str,
            "change_color": color,
        }

    def _placeholder(self, symbol: str) -> dict:
        return {"symbol": symbol, "price": "—", "change": "…", "change_color": (0.72, 0.74, 0.80, 1)}

