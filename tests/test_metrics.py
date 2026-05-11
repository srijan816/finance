"""Tests for quant/metrics.py"""
from quant.metrics import max_drawdown, sharpe_ratio, summarize_performance


def test_summarize_performance_has_core_metrics():
    result = summarize_performance([0.01, -0.005, 0.02], [0.005, 0.001, 0.01])
    assert "sharpe" in result
    assert "alpha" in result
    assert "cvar_95" in result


def test_max_drawdown_is_negative_loss():
    assert max_drawdown([0.1, -0.2, 0.05]) < 0


def test_sharpe_handles_flat_returns():
    assert sharpe_ratio([0.0, 0.0, 0.0]) == 0.0
