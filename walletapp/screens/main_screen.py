from __future__ import annotations

import threading
from collections import defaultdict

from kivy.clock import Clock
from kivy.properties import ListProperty, StringProperty

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

        # placeholder while app fetches live prices
        self.portfolio_total = "Fetching prices..."
        self.system_status   = "Loading live prices..."

        # api is now on backround thread so our
        # ui doesn't freeze
        threading.Thread(
            target=self._fetch_prices,
            args=(app,),
            daemon=True
        ).start()

    def _fetch_prices(self, app) -> None:
        """Runs on a background thread — never touch UI widgets here."""
        try:
            total  = app.backend.get_portfolio_total_usd()
            assets = app.backend.list_assets()
            market = MarketService()

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

        # send results back to the main thread via Clock
        Clock.schedule_once(
            lambda dt: self._update_ui(total, rows, chart_values, legend_lines, status)
        )

    def _update_ui(self, total, rows, chart_values, legend_lines, status) -> None:
        """Runs back on the main thread — safe to update UI widgets here."""
        self.portfolio_total = f"${total:,.2f}"
        self.system_status   = status

        rv = self.ids.get("assets_rv")
        if rv:
            rv.data = rows

        chart  = self.ids.get("assets_pie")
        legend = self.ids.get("assets_legend")
        if chart:
            chart.values = chart_values
        if legend:
            legend.text = "\n".join(legend_lines) if legend_lines else "No assets"

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
