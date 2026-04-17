from __future__ import annotations

from collections import defaultdict

from kivy.properties import ListProperty, StringProperty

from walletapp.screens.base import WalletScreen
from walletapp.services.secure_backend import SecureWalletBackend


class MainScreen(WalletScreen):
    portfolio_total = StringProperty("$0.00")
    vault_status = StringProperty("")
    """Short banner under portfolio total (kept for compatibility)."""

    system_status = StringProperty(
        "Loading…\nOpen Vault if you need to create or unlock the wallet."
    )
    """Multi-line dashboard text: vault, kill switch, holdings, next steps."""

    vault_strip_color = ListProperty([0.45, 0.55, 0.65, 1.0])
    """Left accent bar color: reflects vault state at a glance."""

    def on_pre_enter(self, *args) -> None:
        app = self.manager.app  # type: ignore[attr-defined]
        b = app.backend
        if isinstance(b, SecureWalletBackend):
            if not b.vault_exists():
                self.vault_status = "Create an encrypted vault under Vault to store balances and keys."
                self.vault_strip_color = [0.95, 0.45, 0.35, 1.0]
            elif not b.is_unlocked:
                self.vault_status = "Vault locked — unlock under Vault to view portfolio and transact."
                self.vault_strip_color = [0.95, 0.75, 0.25, 1.0]
            else:
                self.vault_status = ""
                self.vault_strip_color = [0.30, 0.82, 0.55, 1.0]
        else:
            self.vault_status = ""
            self.vault_strip_color = [0.55, 0.60, 0.70, 1.0]

        total = app.backend.get_portfolio_total_usd()
        self.portfolio_total = f"${total:,.2f}"

        assets = app.backend.list_assets()
        self.system_status = self._build_system_status(b, assets, total)
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

    def _build_system_status(self, b, assets: list, total: float) -> str:
        lines: list[str] = ["[b]Status[/b]", ""]
        if isinstance(b, SecureWalletBackend):
            if not b.vault_exists():
                lines.append("• Vault: [b]not created[/b] — tap [i]Vault[/i] in the bar below.")
                lines.append("• Data: nothing stored yet (SQLite + encryption after setup).")
            elif not b.is_unlocked:
                lines.append("• Vault: [b]locked[/b] — enter passphrase on the Vault screen.")
                lines.append("• Portfolio: hidden until unlock.")
            else:
                lines.append("• Vault: [b]unlocked[/b] (keys in memory only while open).")
                prefs = b.load_security_settings()
                ks_on = prefs.get("killswitch_enabled", False)
                lines.append(
                    "• Kill switch: [b]ON[/b] (sends blocked)"
                    if ks_on
                    else "• Kill switch: off"
                )
            lines.append(f"• Holdings rows: {len(assets)}  ·  Est. total: [b]${total:,.2f}[/b]")
            if b.vault_exists() and b.is_unlocked:
                lines.append("")
                lines.append("[i]Try:[/i] New Transaction → Preview → Confirm (testnet demo).")
        else:
            lines.append("• Backend: stub (no encrypted DB).")
            lines.append(f"• Holdings rows: {len(assets)}  ·  Est. total: ${total:,.2f}")
        return "\n".join(lines)

