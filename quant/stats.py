"""Statistical diagnostics for research results."""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def mean_confidence_interval(
    values: Iterable[float],
    confidence: float = 0.95,
    n_boot: int = 2000,
    seed: int = 7,
) -> dict:
    arr = _finite(values)
    if len(arr) == 0:
        return {"mean": 0.0, "lower": 0.0, "upper": 0.0}
    rng = np.random.default_rng(seed)
    samples = rng.choice(arr, size=(n_boot, len(arr)), replace=True).mean(axis=1)
    alpha = (1 - confidence) / 2
    return {
        "mean": float(arr.mean()),
        "lower": float(np.quantile(samples, alpha)),
        "upper": float(np.quantile(samples, 1 - alpha)),
    }


def mean_z_test(values: Iterable[float], null_mean: float = 0.0) -> dict:
    arr = _finite(values)
    if len(arr) < 2:
        return {"z": 0.0, "p_value": 1.0}
    std = float(np.std(arr, ddof=1))
    if std == 0:
        return {"z": 0.0, "p_value": 1.0}
    z = float((arr.mean() - null_mean) / (std / math.sqrt(len(arr))))
    return {"z": z, "p_value": float(math.erfc(abs(z) / math.sqrt(2)))}


def binomial_p_value(successes: int, trials: int, null_probability: float = 0.5) -> float:
    if trials <= 0:
        return 1.0
    if not 0 < null_probability < 1:
        raise ValueError("null_probability must be between 0 and 1")
    observed = successes
    expected = trials * null_probability
    if observed == expected:
        return 1.0
    if observed > expected:
        tail = sum(_binom_prob(k, trials, null_probability) for k in range(observed, trials + 1))
    else:
        tail = sum(_binom_prob(k, trials, null_probability) for k in range(0, observed + 1))
    return float(min(1.0, 2 * tail))


def _binom_prob(k: int, n: int, p: float) -> float:
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def _finite(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr)]
