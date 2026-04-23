from __future__ import annotations

from kivy.properties import ListProperty, StringProperty

from walletapp.models import AssetKind
from walletapp.screens.base import WalletScreen


class AddFundsScreen(WalletScreen):
    status_text = StringProperty("")
    asset_values = ListProperty(["ETH", "USDC", "BTC", "AAPL", "MSFT", "TSLA", "SOL", "BNB", "ADA"])

    def on_pre_enter(self, *args) -> None:
        self.status_text = ""

        app = self.manager.app  # type: ignore[attr-defined]
        # Prefer showing currently held assets at top.
        try:
            assets = app.backend.list_assets()
        except Exception:
            assets = []
        symbols = [a.symbol.upper() for a in assets if getattr(a, "symbol", "")]
        # add some defaults
        defaults = ["ETH", "USDC", "BTC", "AAPL", "MSFT", "TSLA"]
        merged = list(dict.fromkeys(symbols + defaults))
        if merged:
            self.asset_values = merged

    def add_funds(self) -> None:
        self.status_text = ""
        app = self.manager.app  # type: ignore[attr-defined]

        symbol = (self.ids.asset_symbol.text or "").strip().upper()
        amount_str = (self.ids.amount.text or "").strip()

        if not symbol:
            self.status_text = "Pick an asset."
            return
        if not amount_str:
            self.status_text = "Enter an amount."
            return
        try:
            amount = float(amount_str)
        except ValueError:
            self.status_text = "Amount must be a number."
            return
        if amount <= 0:
            self.status_text = "Amount must be greater than 0."
            return

        kind_str = (self.ids.asset_kind.text or "Crypto").strip()
        try:
            kind = AssetKind(kind_str)
        except ValueError:
            kind = AssetKind.CRYPTO

        if not hasattr(app.backend, "credit_asset"):
            self.status_text = "Backend does not support adding funds."
            return

        try:
            app.backend.credit_asset(kind, symbol, amount)
        except Exception as e:
            self.status_text = str(e) or "Failed to add funds."
            return

        self.status_text = f"Added {amount:g} {symbol}."
        try:
            self.ids.amount.text = ""
        except Exception:
            pass

