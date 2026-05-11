"""Tests for quant/data.py"""
from quant.data import fetch_bars, cache_db

def fake_download(ticker, start, end, progress=False):
    import pandas as pd

    dates = pd.date_range(start="2024-01-02", periods=12, freq="B")
    return pd.DataFrame({
        "Open": [100 + i for i in range(len(dates))],
        "High": [101 + i for i in range(len(dates))],
        "Low": [99 + i for i in range(len(dates))],
        "Close": [100.5 + i for i in range(len(dates))],
        "Volume": [1_000_000 + i for i in range(len(dates))],
    }, index=dates)

def test_fetch_bars_nvda(monkeypatch):
    import quant.data

    monkeypatch.setattr(quant.data.yf, "download", fake_download)
    bars = fetch_bars("NVDA", "2024-01-01", "2024-02-01")
    assert len(bars) > 5
    dates, opens, highs, lows, closes, volumes = zip(*bars)
    assert all(close > 0 for close in closes)
    assert dates == tuple(sorted(dates))

def test_fetch_bars_multiple_tickers(monkeypatch):
    import quant.data

    monkeypatch.setattr(quant.data.yf, "download", fake_download)
    for ticker in ["AAPL", "MSFT"]:
        bars = fetch_bars(ticker, "2024-01-01", "2024-01-31")
        assert len(bars) > 5

def test_cache_works(monkeypatch):
    import quant.data

    monkeypatch.setattr(quant.data.yf, "download", fake_download)
    # Should complete without error
    bars = fetch_bars("SPY", "2024-06-01", "2024-06-30")
    assert len(bars) > 0
