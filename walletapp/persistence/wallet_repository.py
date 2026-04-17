"""Persist portfolio holdings with encrypted balances."""

from __future__ import annotations

from walletapp.models import Asset, AssetKind
from walletapp.persistence.database import Database
from walletapp.persistence.encryption import EncryptionService


class WalletRepository:
    def __init__(self, db: Database, crypto: EncryptionService) -> None:
        self._db = db
        self._crypto = crypto

    def get_holdings(self) -> list[Asset]:
        conn = self._db.connect()
        rows = conn.execute(
            "SELECT kind, symbol, balance_ciphertext FROM holdings ORDER BY symbol ASC"
        ).fetchall()
        out: list[Asset] = []
        for row in rows:
            bal_text = self._crypto.decrypt_text(row["balance_ciphertext"])
            out.append(
                Asset(
                    kind=AssetKind(row["kind"]),
                    symbol=row["symbol"],
                    balance=float(bal_text),
                )
            )
        return out

    def save_holdings(self, assets: list[Asset]) -> None:
        conn = self._db.connect()
        conn.execute("DELETE FROM holdings")
        for a in assets:
            ct = self._crypto.encrypt_text(f"{float(a.balance):.12g}")
            conn.execute(
                """
                INSERT INTO holdings (kind, symbol, balance_ciphertext)
                VALUES (?, ?, ?)
                """,
                (a.kind.value, a.symbol.upper(), ct),
            )
        conn.commit()

    def upsert_holding(self, asset: Asset) -> None:
        conn = self._db.connect()
        ct = self._crypto.encrypt_text(f"{float(asset.balance):.12g}")
        conn.execute(
            """
            INSERT INTO holdings (kind, symbol, balance_ciphertext)
            VALUES (?, ?, ?)
            ON CONFLICT(kind, symbol) DO UPDATE SET
              balance_ciphertext = excluded.balance_ciphertext
            """,
            (asset.kind.value, asset.symbol.upper(), ct),
        )
        conn.commit()

    def replace_symbol_balance(self, symbol: str, new_balance: float, kind: AssetKind) -> None:
        conn = self._db.connect()
        ct = self._crypto.encrypt_text(f"{float(new_balance):.12g}")
        cur = conn.execute(
            "SELECT id FROM holdings WHERE kind = ? AND symbol = ? COLLATE NOCASE",
            (kind.value, symbol.upper()),
        )
        row = cur.fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO holdings (kind, symbol, balance_ciphertext) VALUES (?, ?, ?)",
                (kind.value, symbol.upper(), ct),
            )
        else:
            conn.execute(
                "UPDATE holdings SET balance_ciphertext = ? WHERE id = ?",
                (ct, row["id"]),
            )
        conn.commit()
