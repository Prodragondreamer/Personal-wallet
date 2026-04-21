import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from walletapp.services.backend import StubBackend


def test_backend_loads():
    backend = StubBackend()

    backend.market.get_crypto_price = lambda s: 3000.0
    backend.market.get_stock_price  = lambda s: 190.0

    assert backend.get_portfolio_total_usd() >= 0


def test_preview_transaction():
    from walletapp.models import AssetKind, TransactionDraft
    backend = StubBackend()
    backend.market.get_crypto_price = lambda s: 3000.0
    backend.market.get_stock_price  = lambda s: 190.0

    draft   = TransactionDraft(AssetKind.CRYPTO, "ETH", 0.5, "0xABCD")
    preview = backend.preview_transaction(draft)

    assert preview.est_fee > 0
    assert preview.total == draft.amount + preview.est_fee


def test_send_transaction():
    from walletapp.models import AssetKind, TransactionDraft
    backend = StubBackend()
    backend.market.get_crypto_price = lambda s: 3000.0
    backend.market.get_stock_price  = lambda s: 190.0

    draft   = TransactionDraft(AssetKind.CRYPTO, "ETH", 0.5, "0xABCD")
    preview = backend.preview_transaction(draft)
    result  = backend.send_transaction(preview)

    assert result.ok is True
    assert result.tx_hash is not None


def test_insufficient_balance_blocked():
    from walletapp.models import AssetKind, TransactionDraft
    backend = StubBackend()
    backend.market.get_crypto_price = lambda s: 3000.0

    draft   = TransactionDraft(AssetKind.CRYPTO, "ETH", 99999.0, "0xABCD")
    preview = backend.preview_transaction(draft)
    result  = backend.send_transaction(preview)

    assert result.ok is False
    assert "Insufficient" in result.error
