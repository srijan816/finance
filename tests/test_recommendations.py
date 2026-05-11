"""Tests for technical recommendation helpers."""
import pytest

from quant.recommendations import long_entry_plan


def test_long_entry_plan_keeps_stop_below_pullback_entry():
    plan = long_entry_plan(entry=714.79, atr=7.02, support_stop=681.96)
    assert plan.stop < plan.entry
    assert round(plan.stop, 2) == 699.35
    assert plan.target > plan.entry


def test_long_entry_plan_falls_back_when_support_is_above_entry():
    plan = long_entry_plan(entry=100, atr=2, support_stop=101)
    assert plan.stop == pytest.approx(95.6)
    assert plan.stop < plan.entry
