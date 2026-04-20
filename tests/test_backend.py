import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from walletapp.services.backend import StubBackend

def test_backend_loads():
    backend = StubBackend()
    assert backend.get_portfolio_total_usd() >= 0
