"""Tests for calibrated technical v2 engine."""
from datetime import date, timedelta

from quant.technical_v2 import (
    bars_to_frame,
    build_training_samples,
    recommend_from_bars,
    technical_feature_frame,
)


def sample_bars(n=420, start_price=100.0, drift=0.001, volume=1_000_000):
    bars = []
    price = start_price
    start = date(2020, 1, 1)
    for i in range(n):
        price *= 1 + drift + (0.002 if i % 11 == 0 else -0.0003)
        high = price * 1.01
        low = price * 0.99
        bars.append(((start + timedelta(days=i)).isoformat(), price, high, low, price, volume + i * 100))
    return bars


def test_feature_frame_includes_non_arbitrary_v2_features():
    frame = technical_feature_frame(sample_bars(360))
    latest = frame.dropna().iloc[-1]
    assert latest["adx_14"] >= 0
    assert latest["rel_volume_20"] > 0
    assert "weekly_price_vs_sma40" in frame.columns
    assert "bearish_rsi_divergence" in frame.columns


def test_training_samples_use_forward_active_return():
    features = {
        "AAA": technical_feature_frame(sample_bars(420, drift=0.002)),
        "BBB": technical_feature_frame(sample_bars(420, drift=0.0005)),
    }
    benchmark = bars_to_frame(sample_bars(420, drift=0.001))
    samples = build_training_samples(features, benchmark, horizon=21)
    assert len(samples) > 0
    assert "forward_active_return" in samples.columns


def test_recommend_from_bars_produces_entry_specific_stops():
    bars = {
        "AAA": sample_bars(900, start_price=100, drift=0.002),
        "BBB": sample_bars(900, start_price=90, drift=0.001),
        "CCC": sample_bars(900, start_price=80, drift=0.0008),
        "DDD": sample_bars(900, start_price=70, drift=0.0015),
        "EEE": sample_bars(900, start_price=60, drift=0.0006),
    }
    benchmark = sample_bars(900, start_price=100, drift=0.001)
    result = recommend_from_bars(bars, benchmark, horizon=21, top_n=3)
    assert result["model"]["type"] == "standardized_ridge_regression"
    assert result["recommendations"]
    for item in result["recommendations"]:
        assert item["pullback_plan"]["stop"] < item["pullback_plan"]["entry"]
        assert item["breakout_plan"]["stop"] < item["breakout_plan"]["entry"]
        assert item["breakout_plan"]["entry"] >= item["price"]
        assert "weekly_trend" in item["gates"]
