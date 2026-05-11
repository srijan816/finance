"""Tests for quant/simulator.py"""
from datetime import date, timedelta

from quant.simulator import simulate_historical_paper
from quant.simulator import _target_weights


def sample_bars(n=420, start_price=100.0, drift=0.001):
    bars = []
    price = start_price
    start = date(2020, 1, 1)
    for i in range(n):
        price *= 1 + drift + (0.001 if i % 5 else -0.0004)
        bars.append(((start + timedelta(days=i)).isoformat(), price, price, price, price, 1_000_000))
    return bars


def test_simulate_historical_paper(monkeypatch):
    import quant.data

    def fake_fetch(ticker, start, end):
        return sample_bars(420, 400.0 if ticker == "SPY" else 100.0)

    monkeypatch.setattr(quant.data, "fetch_bars", fake_fetch)
    result = simulate_historical_paper(["AAPL", "MSFT"], "2020-01-01", "2025-01-01")
    assert result["initial_capital"] == 10_000
    assert result["final_equity"] > 0
    assert result["n_rebalances"] > 0
    assert "sharpe" in result["metrics"]


def test_target_weights_ignore_future_prices():
    import numpy as np

    day = 80
    flat_then_spike = np.asarray([100.0] * day + [1000.0] * 20)
    steady_momentum = np.asarray([100.0 + i for i in range(day + 20)])
    closes = {
        "FUTURE_SPIKE": flat_then_spike,
        "KNOWN_MOMENTUM": steady_momentum,
    }
    weights = _target_weights(closes, ["FUTURE_SPIKE", "KNOWN_MOMENTUM"], "momentum", day, 1)
    assert weights["KNOWN_MOMENTUM"] == 1.0
    assert weights["FUTURE_SPIKE"] == 0.0


def test_simulator_aligns_by_common_dates(monkeypatch):
    import quant.data

    base = sample_bars(420)
    shifted = base[:100] + base[101:]

    def fake_fetch(ticker, start, end):
        if ticker == "MSFT":
            return shifted
        return base

    monkeypatch.setattr(quant.data, "fetch_bars", fake_fetch)
    result = simulate_historical_paper(["AAPL", "MSFT"], "2020-01-01", "2025-01-01")
    assert result["final_equity"] > 0
    assert result["start"] in {row[0] for row in shifted}


def test_simulator_tracks_monthly_contributions(monkeypatch):
    import quant.data

    def fake_fetch(ticker, start, end):
        return sample_bars(520, 400.0 if ticker == "SPY" else 100.0)

    monkeypatch.setattr(quant.data, "fetch_bars", fake_fetch)
    result = simulate_historical_paper(
        ["AAPL", "MSFT"],
        "2020-01-01",
        "2025-01-01",
        initial_capital=0,
        monthly_contribution=1000,
    )
    assert result["initial_capital"] == 0
    assert result["monthly_contribution"] == 1000
    assert result["n_contributions"] > 0
    assert result["total_contributed"] == sum(item["amount"] for item in result["contributions"])
    assert any(item["months_covered"] >= 1 for item in result["contributions"])
    assert result["final_equity"] > 0
