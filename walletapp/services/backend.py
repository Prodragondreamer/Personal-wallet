from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from walletapp.models import Asset, AssetKind, TransactionDraft, TransactionPreview
from walletapp.services.market_service import MarketService


@dataclass(frozen=True)
class SendResult:
    ok: bool
    tx_hash: str | None = None
    error: str | None = None


class BackendController(Protocol):
    def list_assets(self) -> list[Asset]: ...
    def get_portfolio_total_usd(self) -> float: ...
    def preview_transaction(self, draft: TransactionDraft) -> TransactionPreview: ...
    def send_transaction(self, preview: TransactionPreview) -> SendResult: ...


class StubBackend:
    def __init__(self) -> None:
        self._assets: list[Asset] = [
            Asset(kind=AssetKind.CRYPTO, symbol="ETH",  balance=1.234),
            Asset(kind=AssetKind.CRYPTO, symbol="USDC", balance=250.00),
            Asset(kind=AssetKind.STOCK,  symbol="AAPL", balance=3.0),
        ]
        self.market = MarketService()

    def list_assets(self) -> list[Asset]:
        return list(self._assets)

    def get_portfolio_total_usd(self) -> float:
        total = 0.0

    for a in self._assets:
        symbol = a.symbol.upper()

        try:
            if a.kind == AssetKind.CRYPTO:
                price = self.market.get_crypto_price(symbol.lower())
            elif a.kind == AssetKind.STOCK:
                price = self.market.get_stock_price(symbol)
            else:
                price = 1.0
        except Exception:
            price = 0.0

        total += float(a.balance) * float(price)

    return total
    def preview_transaction(self, draft: TransactionDraft) -> TransactionPreview:
    est_fee = 1.25
    total = float(draft.amount) + est_fee

    return TransactionPreview(
        draft=draft,
        network="Testnet",
        est_fee=est_fee,
        total=total
    )

    def send_transaction(self, preview: TransactionPreview) -> SendResult:
        d     = preview.draft
        debit = float(d.amount)

        for i, a in enumerate(self._assets):
            if a.symbol.upper() != d.symbol.upper():
                continue
            if float(a.balance) < debit:
                return SendResult(ok=False, error="Insufficient balance for amount.")
            self._assets[i] = Asset(
                kind=a.kind, symbol=a.symbol, balance=float(a.balance) - debit
            )
            return SendResult(ok=True, tx_hash="0xDEMO_TX_HASH")

        return SendResult(ok=False, error=f"Unknown asset symbol: {d.symbol}")
