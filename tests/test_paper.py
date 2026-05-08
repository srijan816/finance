"""Tests for quant/paper.py"""
import pytest
from quant.paper import has_keys, account_status, execute_paper

def test_has_keys():
    # Returns False when keys missing (expected in CI)
    result = has_keys()
    assert isinstance(result, bool)

def test_account_status_graceful():
    status = account_status()
    assert isinstance(status, str)
    assert len(status) > 0

def test_execute_paper_no_keys():
    if not has_keys():
        result = execute_paper("buy", "NVDA", 10)
        assert "keys not configured" in result.lower() or "alpaca" in result.lower()