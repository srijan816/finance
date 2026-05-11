"""Tests for allocation policy."""
from quant.allocation import allocate_from_recommendations


def rec(ticker, rank, weekly=True, overbought=False, bearish=False, sector_price=100):
    return {
        "ticker": ticker,
        "price": sector_price,
        "rank_score": rank,
        "predicted_63d_active_return": rank,
        "gates": {
            "daily_trend": True,
            "weekly_trend": weekly,
            "overbought_rsi": overbought,
            "bearish_rsi_divergence": bearish,
            "trend_strength": "moderate",
            "volume_confirmed_breakout": False,
        },
        "pullback_plan": {"entry": sector_price * 0.95, "stop": sector_price * 0.90, "target": sector_price * 1.10},
        "breakout_plan": {"entry": sector_price * 1.01, "stop": sector_price * 0.96, "target": sector_price * 1.15},
    }


def test_allocation_excludes_overbought_bearish_divergence():
    result = allocate_from_recommendations([
        rec("INTC", 0.2, overbought=True, bearish=True),
        rec("NVDA", 0.1),
    ], capital=20_000)
    tickers = [row["ticker"] for row in result["allocations"]]
    assert "INTC" not in tickers
    assert "NVDA" in tickers
    assert result["cash"] >= 2_000


def test_allocation_uses_pullback_when_extended():
    result = allocate_from_recommendations([rec("AMAT", 0.1, sector_price=120)], capital=20_000)
    assert result["allocations"][0]["entry_style"] == "pullback"
    assert result["allocations"][0]["stop"] < result["allocations"][0]["entry"]
