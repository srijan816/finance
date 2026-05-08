"""Tests for quant/data.py"""
import pytest
from quant.data import fetch_bars, cache_db

def test_fetch_bars_nvda():
    bars = fetch_bars("NVDA", "2024-01-01", "2024-02-01")
    assert len(bars) > 5
    dates, opens, highs, lows, closes, volumes = zip(*bars)
    assert all(close > 0 for close in closes)
    assert dates == tuple(sorted(dates))

def test_fetch_bars_multiple_tickers():
    for ticker in ["AAPL", "MSFT"]:
        bars = fetch_bars(ticker, "2024-01-01", "2024-01-31")
        assert len(bars) > 5

def test_cache_works():
    import tempfile
    # Should complete without error
    bars = fetch_bars("SPY", "2024-06-01", "2024-06-30")
    assert len(bars) > 0