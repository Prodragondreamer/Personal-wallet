from __future__ import annotations

from kivy.properties import StringProperty

from walletapp.models import AssetKind, TransactionDraft
from walletapp.screens.base import WalletScreen


class AssetEntryScreen(WalletScreen):
    error_text = StringProperty("")

    def clear_error(self) -> None:
        self.error_text = ""

    def build_draft(self) -> TransactionDraft | None:
        self.clear_error()

        kind_str = (self.ids.asset_kind.text or "").strip()
        symbol = (self.ids.asset_symbol.text or "").strip().upper()
        amount_str = (self.ids.asset_amount.text or "").strip()
        to_address = (self.ids.to_address.text or "").strip()
        memo = (self.ids.memo.text or "").strip()

        if not symbol:
            self.error_text = "Enter an asset symbol (example: ETH)."
            return None
        if not amount_str:
            self.error_text = "Enter an amount."
            return None
        try:
            amount = float(amount_str)
        except ValueError:
            self.error_text = "Amount must be a number."
            return None
        if amount <= 0:
            self.error_text = "Amount must be greater than 0."
            return None
        if not to_address:
            self.error_text = "Enter a destination address."
            return None

        try:
            asset_kind = AssetKind(kind_str)
        except ValueError:
            asset_kind = AssetKind.CRYPTO

        return TransactionDraft(
            asset_kind=asset_kind,
            symbol=symbol,
            amount=amount,
            to_address=to_address,
            memo=memo,
        )

    def go_to_preview(self) -> None:
        draft = self.build_draft()
        if not draft:
            return

        app = self.manager.app  # type: ignore[attr-defined]
        app.state["draft"] = draft
        # Build and store the preview immediately so the Preview screen
        # never ends up with a missing preview state.
        app.state["preview"] = app.backend.preview_transaction(draft)

        # Use the ScreenManager helper so transitions are consistent.
        if hasattr(self.manager, "set_current"):
            self.manager.set_current("tx_preview")  # type: ignore[attr-defined]
        else:
            self.manager.current = "tx_preview"

