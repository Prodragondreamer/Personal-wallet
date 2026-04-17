from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AssetKind(str, Enum):
    CRYPTO = "Crypto"
    STOCK = "Stock"
    CASH = "Cash"


@dataclass(frozen=True)
class Asset:
    kind: AssetKind
    symbol: str
    balance: float


@dataclass(frozen=True)
class TransactionDraft:
    asset_kind: AssetKind
    symbol: str
    amount: float
    to_address: str
    memo: str = ""


@dataclass(frozen=True)
class TransactionPreview:
    draft: TransactionDraft
    network: str
    est_fee: float
    total: float

