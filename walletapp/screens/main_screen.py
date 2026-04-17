from __future__ import annotations

from collections import defaultdict

from kivy.properties import StringProperty

from walletapp.screens.base import WalletScreen
from walletapp.services.secure_backend import SecureWalletBackend


class MainScreen(WalletScreen):
    portfolio_total = StringProperty("$0.00")
    vault_status = StringProperty("")

    def on_pre_enter(self, *args) -> None:
        app = self.manager.app  # type: ignore[attr-defined]
        b = app.backend
        if isinstance(b, SecureWalletBackend):
            if not b.vault_exists():
                self.vault_status = "Create an encrypted vault in Settings to store balances and keys."
            elif not b.is_unlocked:
                self.vault_status = "Vault locked — unlock in Settings to view portfolio and transact."
            else:
                self.vault_status = ""
        else:
            self.vault_status = ""

        total = app.backend.get_portfolio_total_usd()
        self.portfolio_total = f"${total:,.2f}"

        assets = app.backend.list_assets()
        rv = self.ids.get("assets_rv")
        if rv:
            rv.data = [
                {"text": f"{a.symbol}  •  {a.kind}  •  {a.balance:g}"}
                for a in assets
            ]

        # Pie chart (by symbol, so slices map to ETH/USDC/etc).
        by_symbol: dict[str, float] = defaultdict(float)
        for a in assets:
            by_symbol[a.symbol.upper()] += float(a.balance)

        chart = self.ids.get("assets_pie")
        legend = self.ids.get("assets_legend")
        if chart:
            palette = {
                "ETH": (0.22, 0.45, 0.95, 0.95),
                "USDC": (0.25, 0.80, 0.65, 0.95),
                "AAPL": (0.95, 0.75, 0.30, 0.95),
            }
            values = []
            legend_lines = []
            total = sum(by_symbol.values()) or 1.0
            for sym, v in sorted(by_symbol.items(), key=lambda kv: kv[0]):
                rgba = palette.get(sym, (0.75, 0.55, 0.95, 0.90))
                values.append((v, *rgba))
                pct = (v / total) * 100.0
                legend_lines.append(f"{sym}: {pct:0.1f}%  ({v:g})")

            chart.values = values
            if legend:
                legend.text = "\n".join(legend_lines) if legend_lines else "No assets"

