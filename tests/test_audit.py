"""Tests for quant/audit.py"""
from quant.audit import audit_universe_decisions, generate_historical_decisions, summarize_decisions


def sample_bars(n=360, start_price=100.0, drift=0.001):
    bars = []
    price = start_price
    for i in range(n):
        price *= 1 + drift + (0.001 if i % 5 else -0.0003)
        bars.append((f"2024-01-{(i % 28) + 1:02d}", price, price, price, price, 1_000_000))
    return bars


def test_generate_historical_decisions_uses_future_only_for_scoring():
    bars = sample_bars()
    decisions = generate_historical_decisions(
        ticker="AAPL",
        bars=bars,
        strategy="momentum",
        benchmark_bars=sample_bars(start_price=400.0, drift=0.0005),
        min_history=100,
        horizon=21,
        step=21,
    )
    assert decisions
    first = decisions[0]
    assert first.decision_date == bars[99][0]
    assert first.entry_date == bars[100][0]
    assert first.exit_date == bars[121][0]
    assert first.decision in {"BUY", "HOLD"}


def test_summarize_decisions_has_calibration():
    decisions = generate_historical_decisions(
        ticker="AAPL",
        bars=sample_bars(),
        strategy="sma_cross",
        benchmark_bars=sample_bars(start_price=400.0),
        min_history=100,
        horizon=21,
        step=21,
    )
    summary = summarize_decisions(decisions)
    assert summary["n_decisions"] > 0
    assert "brier_score" in summary
    assert isinstance(summary["calibration"], list)


def test_audit_universe_decisions(monkeypatch):
    import quant.data

    monkeypatch.setattr(quant.data, "fetch_bars", lambda ticker, start, end: sample_bars(start_price=400.0 if ticker == "SPY" else 100.0))
    result = audit_universe_decisions(["AAPL", "MSFT"], "2020-01-01", "2025-01-01", min_history=100)
    assert result["summary"]["n_decisions"] > 0
    assert set(result["per_ticker"]) == {"AAPL", "MSFT"}
