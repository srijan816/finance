"""Tests for quant/execution.py"""
from quant.execution import BrokerSimulator, ExecutionConfig, Order


def test_buy_order_charges_fee_and_slippage():
    broker = BrokerSimulator(1_000, ExecutionConfig(commission_bps=10, slippage_bps=10))
    broker.execute_order(Order("2024-01-01", "AAPL", "buy", 5, 100), "2024-01-01", 1_000_000)
    assert broker.positions["AAPL"] == 5
    assert broker.cash < 500
    assert broker.cost_summary()["fees"] > 0
    assert broker.cost_summary()["slippage"] > 0


def test_default_execution_has_zero_commission_but_keeps_slippage():
    broker = BrokerSimulator(1_000, ExecutionConfig(slippage_bps=10, min_notional=1))
    broker.execute_order(Order("2024-01-01", "AAPL", "buy", 5, 100), "2024-01-01", 1_000_000)
    assert broker.cost_summary()["fees"] == 0
    assert broker.cost_summary()["slippage"] > 0


def test_volume_cap_creates_partial_fill():
    broker = BrokerSimulator(100_000, ExecutionConfig(max_volume_participation=0.1, min_notional=1))
    broker.execute_order(Order("2024-01-01", "AAPL", "buy", 1_000, 100), "2024-01-01", volume=100)
    assert broker.positions["AAPL"] == 10
    assert broker.rejected_orders


def test_insufficient_cash_rejects_when_configured():
    broker = BrokerSimulator(100, ExecutionConfig(reject_if_insufficient_cash=True))
    broker.execute_order(Order("2024-01-01", "AAPL", "buy", 10, 100), "2024-01-01", 1_000_000)
    assert "AAPL" not in broker.positions
    assert broker.rejected_orders[0].reason == "insufficient_cash"
