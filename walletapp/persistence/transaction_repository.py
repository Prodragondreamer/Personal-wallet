from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from walletapp.models import TransactionPreview
from walletapp.persistence.database import Database
from walletapp.services.backend import SendResult


@dataclass(frozen=True)
class TransactionRecord:
    id: int
    created_at: str
    symbol: str
    amount: float
    to_address: str
    network: str
    status: str
    tx_hash: str | None
    error: str | None


def _utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class TransactionRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    def log_preview(self, preview: TransactionPreview, *, status: str = "pending") -> int:
        d = preview.draft
        conn = self._db.connect()
        cur = conn.execute(
            """
            INSERT INTO transactions (
                created_at, asset_kind, symbol, amount, to_address, memo,
                network, est_fee, total, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now_str(),
                d.asset_kind.value,
                d.symbol,
                float(d.amount),
                d.to_address,
                d.memo or "",
                preview.network,
                float(preview.est_fee),
                float(preview.total),
                status,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)

    def update_result(self, tx_id: int, result: SendResult) -> None:
        status = "confirmed" if result.ok else "failed"
        if not result.ok and result.error and "Kill switch" in result.error:
            status = "blocked"
        conn = self._db.connect()
        conn.execute(
            "UPDATE transactions SET status=?, tx_hash=?, error=? WHERE id=?",
            (status, result.tx_hash, result.error, int(tx_id)),
        )
        conn.commit()

    def list_recent(self, limit: int = 50) -> list[TransactionRecord]:
        conn = self._db.connect()
        try:
            rows = conn.execute(
                """
                SELECT id, created_at, symbol, amount, to_address, network, status, tx_hash, error
                FROM transactions
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
        except sqlite3.OperationalError:
            # If a user somehow has an ancient DB without the table.
            return []

        out: list[TransactionRecord] = []
        for r in rows:
            out.append(
                TransactionRecord(
                    id=int(r["id"]),
                    created_at=str(r["created_at"]),
                    symbol=str(r["symbol"]),
                    amount=float(r["amount"]),
                    to_address=str(r["to_address"]),
                    network=str(r["network"]),
                    status=str(r["status"]),
                    tx_hash=(str(r["tx_hash"]) if r["tx_hash"] is not None else None),
                    error=(str(r["error"]) if r["error"] is not None else None),
                )
            )
        return out

