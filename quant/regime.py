"""Simple point-in-time market regime classification."""
from __future__ import annotations

from typing import Sequence

import numpy as np


def classify_market_regime(closes: Sequence[float], lookback: int = 63) -> dict:
    """Classify trend/volatility regime using only supplied price history."""
    prices = np.asarray(list(closes), dtype=float)
    prices = prices[np.isfinite(prices)]
    if len(prices) < max(lookback, 20) + 1:
        return {"regime": "insufficient_history", "confidence": 0.0}
    returns = prices[1:] / prices[:-1] - 1
    recent = returns[-lookback:]
    trend = prices[-1] / prices[-lookback] - 1
    vol = float(np.std(recent, ddof=1) * np.sqrt(252))
    if vol >= 0.35 and trend < -0.05:
        regime = "crisis_downtrend"
    elif trend > 0.08 and vol < 0.30:
        regime = "bull_trend"
    elif trend < -0.08:
        regime = "bear_trend"
    elif vol >= 0.30:
        regime = "high_vol_chop"
    else:
        regime = "low_vol_chop"
    confidence = min(1.0, abs(trend) / 0.15 + max(vol - 0.15, 0) / 0.40)
    return {
        "regime": regime,
        "confidence": round(float(confidence), 4),
        "lookback": lookback,
        "trend_return": round(float(trend), 6),
        "annualized_volatility": round(float(vol), 6),
    }
