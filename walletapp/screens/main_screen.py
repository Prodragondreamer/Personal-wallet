from __future__ import annotations

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
    system_status     = StringProperty(
        "Loading…\nOpen Vault if you need to create or unlock the wallet."
    )
    vault_strip_color = ListProperty([0.45, 0.55, 0.65, 1.0])
    is_fetching       = BooleanProperty(False)  # KV binds to this for the indicator
    _loaded           = BooleanProperty(False)  # True after first successful load

    selected_symbol = StringProperty("")
    selected_range = StringProperty("Week")  # Day|Week|Month|Year|All
    chart_points = ListProperty([])  # list[float]
    chart_color = ListProperty([0.95, 0.80, 0.20, 1.0])
    chart_value_label = StringProperty("")

    _history_cache: dict[tuple[str, str], list[float]] = {}
    _kind_by_symbol: dict[str, str] = {}

    def on_pre_enter(self, *args) -> None:
        app = self.manager.app  # type: ignore[attr-defined]
        b   = app.backend

        if isinstance(b, SecureWalletBackend):
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
        self._refresh_chart()

    def _refresh_chart(self) -> None:
        sym = (self.selected_symbol or "").strip().upper()
        rng = (self.selected_range or "Week").strip().title()
        if not sym:
            self.chart_points = []
            self.chart_value_label = ""
            return

        key = (sym, rng)
        if key not in self._history_cache:
            market = MarketService()
            kind = self._kind_by_symbol.get(sym, "Crypto")
            self._history_cache[key] = market.get_history(sym, kind, rng)
        pts = list(self._history_cache[key])
        self.chart_points = pts
        if pts:
            self.chart_value_label = f"{sym} • ${pts[-1]:,.2f}"

    def on_chart_hover(self, value: float) -> None:
        sym = (self.selected_symbol or "").strip().upper()
        if not sym:
            return
        try:
            v = float(value)
        except Exception:
            return
        if v > 0:
            self.chart_value_label = f"{sym} • ${v:,.2f}"

    def _fetch_prices(self, app) -> None:
        """Runs on a background thread — never touch UI widgets here."""
        try:
            total  = app.backend.get_portfolio_total_usd()
            assets = app.backend.list_assets()
            market = MarketService()

            self._kind_by_symbol = {a.symbol.upper(): a.kind.value for a in assets}

            rows = []
            for a in assets:
                price     = market.get_price(a.symbol, a.kind.value)
                usd_value = float(a.balance) * price
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
