from walletapp.services.backend import StubBackend

def test_backend_loads():
    backend = StubBackend()
    assert backend.get_portfolio_total_usd() >= 0
