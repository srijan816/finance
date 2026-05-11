"""Tests for quant/stats.py"""
from quant.stats import binomial_p_value, mean_confidence_interval, mean_z_test


def test_mean_confidence_interval_bounds_mean():
    result = mean_confidence_interval([0.01, 0.02, 0.03], n_boot=200)
    assert result["lower"] <= result["mean"] <= result["upper"]


def test_mean_z_test_detects_positive_mean():
    result = mean_z_test([0.01, 0.02, 0.03, 0.04])
    assert result["z"] > 0
    assert 0 <= result["p_value"] <= 1


def test_binomial_p_value_range():
    assert 0 <= binomial_p_value(60, 100) <= 1
