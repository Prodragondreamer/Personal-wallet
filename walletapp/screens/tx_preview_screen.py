from __future__ import annotations

from kivy.clock import Clock
from kivy.properties import StringProperty

from walletapp.models import TransactionDraft, TransactionPreview
from walletapp.screens.base import WalletScreen


class TransactionPreviewScreen(WalletScreen):
    summary_text = StringProperty("")
    status_text = StringProperty("")

    def on_pre_enter(self, *args) -> None:
        self.status_text = ""

        app = self.manager.app  # type: ignore[attr-defined]
        preview: TransactionPreview | None = app.state.get("preview")
        if preview:
            self.summary_text = self._format_preview(preview)
            return

        draft: TransactionDraft | None = app.state.get("draft")
        if not draft:
            self.summary_text = "No draft transaction yet."
            return

        preview = app.backend.preview_transaction(draft)
        app.state["preview"] = preview
        self.summary_text = self._format_preview(preview)

    def _format_preview(self, preview: TransactionPreview) -> str:
        d = preview.draft
        memo_part = f"\nMemo: {d.memo}" if d.memo else ""
        return (
            f"Asset: {d.symbol} ({d.asset_kind.value})\n"
            f"Amount: {d.amount:g}\n"
            f"To: {d.to_address}\n"
            f"Network: {preview.network}\n"
            f"Estimated fee: {preview.est_fee:g}\n"
            f"Total: {preview.total:g}"
            f"{memo_part}"
        )

    def confirm_send(self) -> None:
        self.status_text = ""
        app = self.manager.app  # type: ignore[attr-defined]

        preview: TransactionPreview | None = app.state.get("preview")
        if not preview:
            # Try to recover from any navigation edge-cases.
            draft: TransactionDraft | None = app.state.get("draft")
            if not draft:
                self.status_text = "Missing preview. Go back and try again."
                return
            preview = app.backend.preview_transaction(draft)
            app.state["preview"] = preview
            self.summary_text = self._format_preview(preview)

        result = app.backend.send_transaction(preview)
        if result.ok:
            self.status_text = f"Sent. Tx hash: {result.tx_hash}"
            # Clear draft/preview after a successful send.
            app.state.pop("draft", None)
            app.state.pop("preview", None)

            def _go_home(_dt: float) -> None:
                # Navigate after a short delay so the user sees feedback.
                self.manager.set_current("main")  # type: ignore[attr-defined]
                try:
                    main = self.manager.get_screen("main")  # type: ignore[attr-defined]
                    main.on_pre_enter()
                except Exception:
                    pass

            Clock.schedule_once(_go_home, 0.7)
        else:
            self.status_text = result.error or "Transaction failed."

