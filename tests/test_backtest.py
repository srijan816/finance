"""Tests for quant/backtest.py"""
from quant.backtest import run_backtest

def sample_bars(n=90, start_price=100.0, drift=0.002):
    bars = []
    price = start_price
    for i in range(n):
        price *= 1 + drift + (0.001 if i % 3 == 0 else -0.0005)
        bars.append((f"2024-01-{(i % 28) + 1:02d}", price, price, price, price, 1_000_000))
    return bars

def test_backtest_returns_structure(monkeypatch):
    import quant.data

    def fake_fetch(ticker, start, end):
        return sample_bars(90, 400.0 if ticker == "SPY" else 100.0)

    monkeypatch.setattr(quant.data, "fetch_bars", fake_fetch)
    result = run_backtest(["AAPL"], "2024-01-01", "2024-03-01", "agent")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["ticker"] == "AAPL"
    assert "sharpe" in result[0]
    assert "max_dd" in result[0]
    assert "win_rate" in result[0]
    assert "alpha" in result[0]
    assert "assumptions" in result[0]

def test_backtest_multiple_tickers(monkeypatch):
    import quant.data

    def fake_fetch(ticker, start, end):
        return sample_bars(100, 400.0 if ticker == "SPY" else 100.0)

    monkeypatch.setattr(quant.data, "fetch_bars", fake_fetch)
    result = run_backtest(["NVDA", "AAPL"], "2024-01-01", "2024-06-01", "agent")
    assert len(result) == 2
    tickers = {r["ticker"] for r in result}
    assert tickers == {"NVDA", "AAPL"}

def test_backtest_applies_costs(monkeypatch):
    import quant.data

    def fake_fetch(ticker, start, end):
        return sample_bars(120, 400.0 if ticker == "SPY" else 100.0)

    monkeypatch.setattr(quant.data, "fetch_bars", fake_fetch)
    low_cost = run_backtest(["AAPL"], "2024-01-01", "2024-06-01", "momentum", commission_bps=0, slippage_bps=0)[0]
    high_cost = run_backtest(["AAPL"], "2024-01-01", "2024-06-01", "momentum", commission_bps=100, slippage_bps=100)[0]
    assert high_cost["final_equity"] <= low_cost["final_equity"]
