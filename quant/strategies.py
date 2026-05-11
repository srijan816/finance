"""Deterministic research strategies used by the backtester."""
from __future__ import annotations

from typing import Iterable

import numpy as np


def prices_to_returns(closes: Iterable[float]) -> np.ndarray:
    prices = np.asarray(list(closes), dtype=float)
    if len(prices) < 2:
        return np.asarray([], dtype=float)
    return prices[1:] / prices[:-1] - 1


def buy_hold_signal(closes: Iterable[float]) -> np.ndarray:
    prices = np.asarray(list(closes), dtype=float)
    return np.ones(len(prices), dtype=float)


def sma_cross_signal(closes: Iterable[float], fast: int = 20, slow: int = 50) -> np.ndarray:
    prices = np.asarray(list(closes), dtype=float)
    if fast <= 0 or slow <= 0:
        raise ValueError("SMA windows must be positive")
    if fast >= slow:
        raise ValueError("fast SMA window must be shorter than slow SMA window")
    signal = np.zeros(len(prices), dtype=float)
    if len(prices) < slow:
        return signal

    fast_ma = _rolling_mean(prices, fast)
    slow_ma = _rolling_mean(prices, slow)
    signal[(fast_ma > slow_ma) & np.isfinite(slow_ma)] = 1.0
    return signal


def momentum_signal(closes: Iterable[float], lookback: int = 63) -> np.ndarray:
    prices = np.asarray(list(closes), dtype=float)
    if lookback <= 0:
        raise ValueError("momentum lookback must be positive")
    signal = np.zeros(len(prices), dtype=float)
    if len(prices) <= lookback:
        return signal
    momentum = prices / np.roll(prices, lookback) - 1
    momentum[:lookback] = np.nan
    signal[momentum > 0] = 1.0
    return signal


def signal_for_strategy(strategy: str, closes: Iterable[float]) -> np.ndarray:
    name = strategy.lower().replace("-", "_")
    if name in {"buy_hold", "buyhold", "hold"}:
        return buy_hold_signal(closes)
    if name in {"agent", "sma", "sma_cross"}:
        return sma_cross_signal(closes)
    if name in {"momentum", "trend"}:
        return momentum_signal(closes)
    raise ValueError(f"Unknown strategy: {strategy}")


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    result = np.full(len(values), np.nan, dtype=float)
    if len(values) < window:
        return result
    cumsum = np.cumsum(np.insert(values, 0, 0.0))
    result[window - 1:] = (cumsum[window:] - cumsum[:-window]) / window
    return result
