from __future__ import annotations

import math
import random
import threading
from collections import defaultdict

from kivy.clock import Clock
from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.button import Button
from kivy.factory import Factory

from walletapp.screens.base import WalletScreen
from walletapp.services.market_service import MarketService
from walletapp.services.secure_backend import SecureWalletBackend


class MainScreen(WalletScreen):
    portfolio_total   = StringProperty("$0.00")
    vault_status      = StringProperty("")
    vault_exists      = BooleanProperty(False)
    vault_unlocked    = BooleanProperty(False)
    system_status     = StringProperty(
        "Loading…\nOpen Vault if you need to create or unlock the wallet."
    )
    vault_strip_color = ListProperty([0.45, 0.55, 0.65, 1.0])
    is_fetching       = BooleanProperty(False)  # KV binds to this for the indicator
    _loaded           = BooleanProperty(False)  # True after first successful load

    selected_symbol = StringProperty("")
    selected_range = StringProperty("Week")  # Day|Week|Month|Year|All
    selected_zoom = StringProperty("1h")  # resolution varies by range
    zoom_values = ListProperty([])  # values for the zoom picker
    chart_points = ListProperty([])  # list[float]
    chart_labels = ListProperty([])  # list[str]
    chart_color = ListProperty([0.95, 0.80, 0.20, 1.0])
    chart_value_label = StringProperty("")

    _history_cache: dict[tuple[str, str, str], tuple[list[str], list[float]]] = {}
    _kind_by_symbol: dict[str, str] = {}
    _history_inflight: set[tuple[str, str, str]] = set()
    _preload_started: set[tuple[str, str, str]] = set()
    _market: MarketService | None = None

    def on_pre_enter(self, *args) -> None:
        if self._market is None:
            self._market = MarketService()
        self._sync_zoom_defaults()
        app = self.manager.app  # type: ignore[attr-defined]
        b   = app.backend

        if isinstance(b, SecureWalletBackend):
            self.vault_exists = bool(b.vault_exists())
            self.vault_unlocked = bool(b.is_unlocked)
            if not b.vault_exists():
                self.vault_status      = "Create an encrypted vault under Vault."
                self.vault_strip_color = [0.95, 0.45, 0.35, 1.0]
            elif not b.is_unlocked:
                self.vault_status      = "Vault locked — unlock under Vault to view portfolio."
                self.vault_strip_color = [0.95, 0.75, 0.25, 1.0]
            else:
                self.vault_status      = ""
                self.vault_strip_color = [0.30, 0.82, 0.55, 1.0]
        else:
            self.vault_status      = ""
            self.vault_strip_color = [0.55, 0.60, 0.70, 1.0]
            self.vault_exists = False
            self.vault_unlocked = True

        # First load — show placeholder text
        # Refreshes — keep last values visible, just show the indicator
        if not self._loaded:
            self.portfolio_total = "Fetching prices..."
            self.system_status   = "Loading live prices..."

        # Prevent overlapping fetches
        if self.is_fetching:
            return

        self.is_fetching = True  # triggers ⟳ Updating... label in KV
        threading.Thread(
            target=self._fetch_prices,
            args=(app,),
            daemon=True
        ).start()

    def select_asset(self, symbol: str) -> None:
        self.selected_symbol = (symbol or "").strip().upper()
        chips = self.ids.get("asset_chips")
        if chips:
            try:
                for child in chips.children:
                    if hasattr(child, "selected"):
                        child.selected = (getattr(child, "text", "").upper() == self.selected_symbol)
            except Exception:
                pass
        self._refresh_chart()

    def select_range(self, label: str) -> None:
        self.selected_range = (label or "Week").strip().title()
        self._sync_zoom_defaults(reset=True)
        self._refresh_chart()

    def set_zoom(self, label: str) -> None:
        self.selected_zoom = (label or "").strip()
        self._refresh_chart()

    def _sync_zoom_defaults(self, *, reset: bool = False) -> None:
        """
        Provide sensible zoom options per range.
        """
        rng = (self.selected_range or "Week").strip().title()
        if rng == "Day":
            vals = ["30m", "20m", "15m", "10m", "5m", "1m"]
        elif rng == "Week":
            vals = ["4h", "2h", "1h", "30m", "15m"]
        elif rng == "Month":
            vals = ["1d", "12h", "6h", "1h"]
        elif rng == "Year":
            vals = ["1wk", "1d"]
        else:  # All
            vals = ["3mo", "1mo"]
        self.zoom_values = vals
        if reset or (self.selected_zoom not in vals):
            self.selected_zoom = vals[2] if rng == "Week" else vals[0]

    def _zoom_minutes(self) -> int | None:
        """
        Convert selected_zoom into minutes for resampling/bucketing.
        Supports: Xm, Xh, Xd, Xwk, Xmo.
        """
        raw = (self.selected_zoom or "").strip().lower().replace(" ", "")
        if not raw:
            return None
        try:
            if raw.endswith("mo"):
                n = int(raw[:-2])
                return n * 43_200  # 30d
            if raw.endswith("wk"):
                n = int(raw[:-2])
                return n * 10_080
            if raw.endswith("d"):
                n = int(raw[:-1])
                return n * 1_440
            if raw.endswith("h"):
                n = int(raw[:-1])
                return n * 60
            if raw.endswith("m"):
                n = int(raw[:-1])
                return n
            # bare number means minutes
            return int(raw)
        except Exception:
            return None

    def _refresh_chart(self) -> None:
        sym = (self.selected_symbol or "").strip().upper()
        rng = (self.selected_range or "Week").strip().title()
        if not sym:
            self.chart_points = []
            self.chart_value_label = ""
            return

        zoom_min = self._zoom_minutes()
        zoom_key = (self.selected_zoom or "") if zoom_min else ""
        key = (sym, rng, zoom_key)
        cached = self._history_cache.get(key)
        if cached:
            labels, pts = cached
            self.chart_labels = list(labels)
            self.chart_points = list(pts)
            if pts:
                self.chart_value_label = f"{sym} • ${pts[-1]:,.2f}"
            return

        # Don’t block the UI thread waiting on network. Fetch in background.
        market = self._market or MarketService()
        kind = self._kind_by_symbol.get(sym, "Crypto")
        # Instant non-flat placeholder curve so UI never looks stuck.
        spot = float(market.get_price(sym, kind))
        instant = self._instant_series(sym, rng, spot=spot)
        self.chart_labels = ["" for _ in range(len(instant))]
        self.chart_points = list(instant)
        self.chart_value_label = f"{sym} • ${instant[-1]:,.2f}"
        if key in self._history_inflight:
            return
        self._history_inflight.add(key)

        def _fetch_history() -> None:
            labels: list[str] = []
            pts: list[float] = []
            try:
                market2 = self._market or MarketService()
                kind2 = self._kind_by_symbol.get(sym, "Crypto")
                labels, pts = market2.get_history_series(sym, kind2, rng, interval_minutes=zoom_min)
            except Exception:
                labels, pts = ([], [])

            def _apply(_dt: float) -> None:
                self._history_inflight.discard(key)
                if len(pts) >= 2:
                    self._history_cache[key] = (list(labels), list(pts))
                # Only apply if user is still on same selection.
                if (self.selected_symbol or "").strip().upper() != sym:
                    return
                if (self.selected_range or "Week").strip().title() != rng:
                    return
                if len(pts) >= 2:
                    self.chart_labels = list(labels)
                    self.chart_points = list(pts)
                    self.chart_value_label = f"{sym} • ${pts[-1]:,.2f}"

            Clock.schedule_once(_apply)

        threading.Thread(target=_fetch_history, daemon=True).start()

    def _instant_series(self, symbol: str, range_label: str, *, spot: float) -> list[float]:
        """
        Very fast local series (no network) used while real history loads.
        """
        n = {"Day": 24, "Week": 48, "Month": 72, "Year": 96, "All": 120}.get(range_label, 48)
        n = max(24, int(n))
        base = max(0.01, float(spot))
        amp = base * (0.002 if symbol in ("USDC", "USDT", "DAI") else 0.02)
        seed = sum(ord(c) for c in symbol) * 1009 + sum(ord(c) for c in range_label)
        r = random.Random(seed)
        drift = (r.random() - 0.5) * (amp / max(1, n))
        out: list[float] = []
        v = base * (0.99 + 0.02 * r.random())
        for i in range(n):
            t = i / max(1, n - 1)
            wave = math.sin(t * math.pi * 2.0) * (0.6 * amp)
            noise = (r.random() - 0.5) * (0.35 * amp)
            v = max(0.01, v + drift + wave * 0.05 + noise * 0.10)
            out.append(v)
        out[-1] = base
        return out

    def _preload_history(self, symbols: list[str]) -> None:
        """
        Prefetch chart history so taps feel instant.
        Only preloads a small set to avoid rate-limits.
        """
        if not symbols:
            return
        market = self._market or MarketService()
        # Preload current range + Week (most common)
        ranges = list(dict.fromkeys([(self.selected_range or "Week").strip().title(), "Week"]))
        zoom_min = self._zoom_minutes()
        zoom_key = (self.selected_zoom or "") if zoom_min else ""

        def _job() -> None:
            for sym in symbols[:4]:
                kind = self._kind_by_symbol.get(sym, "Crypto")
                for rng in ranges[:2]:
                    k = (sym, rng, zoom_key)
                    if k in self._preload_started or k in self._history_cache:
                        continue
                    self._preload_started.add(k)
                    try:
                        labels, pts = market.get_history_series(sym, kind, rng, interval_minutes=zoom_min)
                        if len(pts) >= 2:
                            self._history_cache[k] = (list(labels), list(pts))
                    except Exception:
                        pass

        threading.Thread(target=_job, daemon=True).start()

    def on_chart_hover(self, value: float, label: str = "") -> None:
        sym = (self.selected_symbol or "").strip().upper()
        if not sym:
            return
        try:
            v = float(value)
        except Exception:
            return
        if v > 0:
            when = (label or "").strip()
            if when:
                self.chart_value_label = f"{sym} • ${v:,.2f} • {when}"
            else:
                self.chart_value_label = f"{sym} • ${v:,.2f}"

    def _fetch_prices(self, app) -> None:
        """Runs on a background thread — never touch UI widgets here."""
        try:
            assets = app.backend.list_assets()
            market = self._market or MarketService()

            self._kind_by_symbol = {a.symbol.upper(): a.kind.value for a in assets}

            crypto_syms = [a.symbol.upper() for a in assets if a.kind.value == "Crypto"]
            stock_syms = [a.symbol.upper() for a in assets if a.kind.value == "Stock"]
            cash_syms = [a.symbol.upper() for a in assets if a.kind.value == "Cash"]

            crypto_q = market.get_crypto_quotes(crypto_syms) if crypto_syms else {}
            stock_q = market.get_stock_quotes(stock_syms) if stock_syms else {}

            rows = []
            total = 0.0
            for a in assets:
                sym = a.symbol.upper()
                if a.kind.value == "Crypto":
                    price = float(crypto_q.get(sym, (market.get_price(sym, "Crypto"), None))[0])
                elif a.kind.value == "Stock":
                    price = float(stock_q.get(sym, (market.get_price(sym, "Stock"), None))[0])
                else:
                    price = float(market.get_price(sym, a.kind.value))
                usd_value = float(a.balance) * price
                total += usd_value
                rows.append({
                    "text": (
                        f"{a.symbol:<6}  "
                        f"{a.balance:>10g}  "
                        f"@ ${price:>10,.2f}  "
                        f"= ${usd_value:>10,.2f}"
                    )
                })

            palette = {
                "ETH":  (0.22, 0.45, 0.95, 0.95),
                "BTC":  (0.98, 0.60, 0.10, 0.95),
                "USDC": (0.25, 0.80, 0.65, 0.95),
                "AAPL": (0.95, 0.75, 0.30, 0.95),
                "TSLA": (0.85, 0.20, 0.20, 0.95),
            }
            by_symbol: dict[str, float] = defaultdict(float)
            for a in assets:
                price = market.get_price(a.symbol, a.kind.value)
                by_symbol[a.symbol.upper()] += float(a.balance) * price

            chart_values = []
            legend_lines = []
            chart_total  = sum(by_symbol.values()) or 1.0
            for sym, usd_val in sorted(by_symbol.items()):
                rgba = palette.get(sym, (0.75, 0.55, 0.95, 0.90))
                chart_values.append((usd_val, *rgba))
                pct = (usd_val / chart_total) * 100.0
                legend_lines.append(f"{sym}: {pct:.1f}%  (${usd_val:,.0f})")

            status = self._build_system_status(app.backend, assets, total)

        except Exception as e:
            total        = 0.0
            rows         = []
            chart_values = []
            legend_lines = ["Error loading prices"]
            status       = f"Error fetching prices: {e}"

        Clock.schedule_once(
            lambda dt: self._update_ui(total, rows, chart_values, legend_lines, status)
        )

    def _update_ui(self, total, rows, chart_values, legend_lines, status) -> None:
        """Runs back on the main thread — safe to update UI widgets here."""
        self.portfolio_total = f"${total:,.2f}"
        self.system_status   = status
        self._loaded         = True
        self.is_fetching     = False  # hides the ⟳ Updating... label

        rv = self.ids.get("assets_rv")
        if rv:
            rv.data = rows

        chart  = self.ids.get("assets_pie")
        legend = self.ids.get("assets_legend")
        if chart:
            chart.values = chart_values
        if legend:
            legend.text = "\n".join(legend_lines) if legend_lines else "No assets"

        chips = self.ids.get("asset_chips")
        if chips:
            try:
                chips.clear_widgets()
                symbols: list[str] = []
                for row in rows:
                    sym = str(row.get("text", "")).strip().split()[0].upper() if row else ""
                    if sym:
                        symbols.append(sym)
                symbols = list(dict.fromkeys(symbols))

                # Start preloading history now that we know which symbols exist.
                self._preload_history(symbols)

                if not self.selected_symbol and symbols:
                    self.selected_symbol = symbols[0]

                palette = {
                    "ETH":  [0.22, 0.45, 0.95, 1.0],
                    "BTC":  [0.98, 0.60, 0.10, 1.0],
                    "USDC": [0.25, 0.80, 0.65, 1.0],
                    "AAPL": [0.95, 0.75, 0.30, 1.0],
                }
                for sym in symbols[:8]:
                    btn = Factory.AssetChip(text=sym)
                    btn.chip_color = palette.get(sym, [0.55, 0.65, 0.95, 1.0])
                    btn.selected = sym == (self.selected_symbol or "").upper()
                    btn.bind(on_release=lambda _btn, s=sym: self.select_asset(s))
                    chips.add_widget(btn)
            except Exception:
                pass

        self.chart_color = {
            "ETH":  [0.22, 0.45, 0.95, 1.0],
            "BTC":  [0.98, 0.60, 0.10, 1.0],
            "USDC": [0.25, 0.80, 0.65, 1.0],
            "AAPL": [0.95, 0.75, 0.30, 1.0],
        }.get((self.selected_symbol or "").upper(), [0.95, 0.80, 0.20, 1.0])
        self._refresh_chart()

    def _build_system_status(self, b, assets: list, total: float) -> str:
        lines: list[str] = ["[b]Status[/b]", ""]
        if isinstance(b, SecureWalletBackend):
            if not b.vault_exists():
                lines.append("• Vault: [b]not created[/b] — tap [i]Vault[/i] in the bar below.")
                lines.append("• Data: nothing stored yet.")
            elif not b.is_unlocked:
                lines.append("• Vault: [b]locked[/b] — enter passphrase on the Vault screen.")
                lines.append("• Portfolio: hidden until unlock.")
            else:
                lines.append("• Vault: [b]unlocked[/b] (keys in memory only while open).")
                prefs = b.load_security_settings()
                ks_on = prefs.get("killswitch_enabled", False)
                lines.append(
                    "• Kill switch: [b]ON[/b] (sends blocked)"
                    if ks_on else
                    "• Kill switch: off"
                )
            lines.append(f"• Holdings rows: {len(assets)}  .  Est. total: [b]${total:,.2f}[/b]")
            if b.vault_exists() and b.is_unlocked:
                lines.append("")
                lines.append("[i]Try:[/i] New Transaction -> Preview -> Confirm (testnet demo).")
        else:
            lines.append("• Backend: stub (no encrypted DB).")
            lines.append(f"• Holdings rows: {len(assets)}  .  Est. total: ${total:,.2f}")
        return "\n".join(lines)
