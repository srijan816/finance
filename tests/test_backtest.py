"""Tests for quant/backtest.py"""
import pytest
from quant.backtest import run_backtest

def test_backtest_returns_structure():
    result = run_backtest(["AAPL"], "2024-01-01", "2024-03-01", "agent")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["ticker"] == "AAPL"
    assert "sharpe" in result[0]
    assert "max_dd" in result[0]
    assert "win_rate" in result[0]

def test_backtest_multiple_tickers():
    result = run_backtest(["NVDA", "AAPL"], "2024-01-01", "2024-06-01", "agent")
    assert len(result) == 2
    tickers = {r["ticker"] for r in result}
    assert tickers == {"NVDA", "AAPL"}