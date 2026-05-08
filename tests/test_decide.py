"""Tests for quant/decide.py"""
import pytest
from quant.decide import run_analysis, parse_decision

def test_parse_decision_buy():
    result = parse_decision({"decision": "BUY", "confidence": 0.8})
    assert result["verdict"] == "BUY"

def test_parse_decision_sell():
    result = parse_decision({"decision": "SELL", "confidence": 0.7})
    assert result["verdict"] == "SELL"

def test_run_analysis_lightweight():
    # Lightweight mode returns a string, not a full graph
    result = run_analysis("AAPL", "2024-01-15", lightweight=True)
    assert isinstance(result, str)
    assert len(result) > 0