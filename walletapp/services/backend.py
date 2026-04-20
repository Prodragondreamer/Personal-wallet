from walletapp.services.market_service import MarketService

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from walletapp.models import Asset, AssetKind, TransactionDraft, TransactionPreview


@dataclass(frozen=True)
class SendResult:
    ok: bool
    tx_hash: str | None = None
    error: str | None = None


class BackendController(Protocol):
    """
    Frontend-facing interface.

    Swap this implementation later with real logic (API/db/blockchain),
    without changing screen code.
    """

    def list_assets(self) -> list[Asset]: ...

    def get_portfolio_total_usd(self) -> float: ...

    def preview_transaction(self, draft: TransactionDraft) -> TransactionPreview: ...

    def send_transaction(self, preview: TransactionPreview) -> SendResult: ...


class StubBackend:
    """
    A safe placeholder backend so the UI works end-to-end.
    Replace with real services later.
    """
def __init__(self) -> None:
    self._assets: list[Asset] = [
        Asset(kind=AssetKind.CRYPTO, symbol="ETH", balance=1.234),
        Asset(kind=AssetKind.CRYPTO, symbol="USDC", balance=250.00),
        Asset(kind=AssetKind.STOCK, symbol="AAPL", balance=3.0),
    ]

    self.market = MarketService()

        # Very rough placeholder pricing so portfolio + chart can change
        # when balances change. Replace with real API pricing later.
     #   self._prices_usd: dict[str, float] = {
        #    "USDC": 1.00,
      #      "ETH": 3000.00,
       #     "AAPL": 190.00,
      #  } 

    def list_assets(self) -> list[Asset]:
        return list(self._assets)

    def get_portfolio_total_usd(self) -> float:
        total = 0.0
        for a in self._assets:
    symbol = a.symbol.upper()

    if symbol in ["ETH", "BTC"]:
        price = self.market.get_crypto_price(symbol.lower())
    elif symbol in ["AAPL"]:
        price = self.market.get_stock_price(symbol)
    else:
        price = 1.0

    total += float(a.balance) * float(price)
        return total

    def preview_transaction(self, draft: TransactionDraft) -> TransactionPreview:
        est_fee = 1.25
        total = draft.amount + est_fee
        return TransactionPreview(draft=draft, network="Testnet", est_fee=est_fee, total=total)

    def send_transaction(self, preview: TransactionPreview) -> SendResult:
        d = preview.draft
        # MVP behavior: deduct ONLY the asset amount.
        # Fees are network-dependent and may be paid in a different token.
        debit = float(d.amount)

        # Deduct from the matching asset symbol.
        for i, a in enumerate(self._assets):
            if a.symbol.upper() != d.symbol.upper():
                continue

            if float(a.balance) < debit:
                return SendResult(ok=False, error="Insufficient balance for amount.")

            self._assets[i] = Asset(kind=a.kind, symbol=a.symbol, balance=float(a.balance) - debit)
            return SendResult(ok=True, tx_hash="0xDEMO_TX_HASH")

        return SendResult(ok=False, error=f"Unknown asset symbol: {d.symbol}")

