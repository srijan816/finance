"""Tests for quant/validation.py"""
from quant.validation import walk_forward_validate


def sample_bars(n=420, start_price=100.0):
    bars = []
    price = start_price
    for i in range(n):
        price *= 1.001 if i % 5 else 0.999
        bars.append((f"2024-01-{(i % 28) + 1:02d}", price, price, price, price, 1_000_000))
    return bars


def test_walk_forward_validate(monkeypatch):
    import quant.data

    monkeypatch.setattr(quant.data, "fetch_bars", lambda ticker, start, end: sample_bars(420))
    result = walk_forward_validate("AAPL", "2020-01-01", "2025-01-01", train_bars=252, test_bars=63)
    assert result["summary"]["n_valid"] > 0
    assert result["summary"]["n_windows"] > 0
