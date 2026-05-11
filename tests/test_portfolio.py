"""Tests for quant/portfolio.py"""
import numpy as np

from quant.portfolio import optimize_portfolio, weights_for_method


def sample_bars(n=90, start_price=100.0, drift=0.001):
    bars = []
    price = start_price
    for i in range(n):
        price *= 1 + drift + (0.001 if i % 4 == 0 else -0.0002)
        bars.append((f"2024-01-{(i % 28) + 1:02d}", price, price, price, price, 1_000_000))
    return bars


def test_weights_sum_to_one():
    returns = np.asarray([[0.01, 0.02], [0.00, 0.01], [0.02, -0.01], [0.01, 0.00]])
    weights = weights_for_method(returns, "min_variance")
    assert round(float(weights.sum()), 8) == 1.0
    assert all(weights >= 0)


def test_optimize_portfolio(monkeypatch):
    import quant.data

    def fake_fetch(ticker, start, end):
        return sample_bars(100, 400.0 if ticker == "SPY" else 100.0, 0.001 if ticker != "MSFT" else 0.0008)

    monkeypatch.setattr(quant.data, "fetch_bars", fake_fetch)
    result = optimize_portfolio(["AAPL", "MSFT"], "2024-01-01", "2024-06-01")
    assert set(result["weights"]) == {"AAPL", "MSFT"}
    assert round(sum(result["weights"].values()), 4) == 1.0
    assert "sharpe" in result["metrics"]
