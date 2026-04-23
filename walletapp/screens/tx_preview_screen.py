from __future__ import annotations

from kivy.clock import Clock
from kivy.properties import StringProperty

from walletapp.models import TransactionDraft, TransactionPreview
from walletapp.screens.base import WalletScreen


class TransactionPreviewScreen(WalletScreen):
    summary_text = StringProperty("")
    status_text = StringProperty("")
    history_text = StringProperty("")

    def on_pre_enter(self, *args) -> None:
        self.status_text = ""

        app = self.manager.app  # type: ignore[attr-defined]
        self._refresh_history(app)

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

    def _refresh_history(self, app) -> None:
        backend = getattr(app, "backend", None)
        if backend is None or not hasattr(backend, "list_transactions"):
            self.history_text = ""
            return

        try:
            txs = backend.list_transactions(limit=50)
        except Exception:
            txs = []

        if not txs:
            self.history_text = "No transactions yet."
            return

        lines: list[str] = []
        for t in txs:
            status = (getattr(t, "status", "") or "").upper()
            symbol = getattr(t, "symbol", "")
            amount = getattr(t, "amount", 0.0)
            network = getattr(t, "network", "")
            to_address = getattr(t, "to_address", "")
            created_at = getattr(t, "created_at", "")
            tx_hash = getattr(t, "tx_hash", None)
            error = getattr(t, "error", None)

            base = f"{created_at}\n{status} • {amount:g} {symbol} • {network}\nTo: {to_address}"
            if tx_hash:
                base += f"\nTx: {tx_hash}"
            if error and not getattr(t, "ok", False):
                base += f"\nError: {error}"
            lines.append(base)

        self.history_text = "\n\n—\n\n".join(lines)

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

        tx_id: int | None = None
        if hasattr(app.backend, "log_transaction_preview"):
            try:
                tx_id = app.backend.log_transaction_preview(preview)
            except Exception:
                tx_id = None

        result = app.backend.send_transaction(preview)

        if tx_id is not None and hasattr(app.backend, "log_transaction_result"):
            try:
                app.backend.log_transaction_result(tx_id, result)
            except Exception:
                pass

        self._refresh_history(app)
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

