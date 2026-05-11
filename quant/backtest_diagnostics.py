"""Backtest overfitting and Sharpe-ratio diagnostics."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np


def sharpe_ratio(returns: Sequence[float], periods_per_year: int = 252) -> float:
    values = np.asarray(list(returns), dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 2:
        return 0.0
    vol = float(np.std(values, ddof=1))
    if vol <= 1e-12:
        return 0.0
    return float(np.mean(values) / vol * math.sqrt(periods_per_year))


def deflated_sharpe_probability(
    sharpe: float,
    n_observations: int,
    n_trials: int = 1,
    benchmark_sharpe: float = 0.0,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> dict:
    """Return a DSR-style probability adjusted for multiple trials and non-normality.

    This is a lightweight implementation of the Bailey/Lopez de Prado idea, using
    the probabilistic Sharpe denominator and a Bonferroni-style multiple-testing
    penalty. It is intentionally labeled as approximate in the output.
    """
    if n_observations <= 1:
        return {"probability": 0.0, "z": 0.0, "adjusted_p_value": 1.0, "method": "approximate_dsr"}
    n_trials = max(int(n_trials), 1)
    numerator = (sharpe - benchmark_sharpe) * math.sqrt(max(n_observations - 1, 1))
    denominator = math.sqrt(max(1 - skew * sharpe + ((kurtosis - 1) / 4) * sharpe * sharpe, 1e-12))
    z = numerator / denominator
    p_one_sided = 1 - _normal_cdf(z)
    adjusted_p = min(1.0, p_one_sided * n_trials)
    return {
        "probability": round(1 - adjusted_p, 6),
        "z": round(z, 6),
        "adjusted_p_value": round(adjusted_p, 6),
        "n_trials": n_trials,
        "method": "approximate_dsr_bonferroni",
    }


def probability_of_backtest_overfitting(
    in_sample_scores: Sequence[float],
    out_of_sample_scores: Sequence[float],
) -> dict:
    """Estimate PBO as the share of IS-selected trials below OOS median.

    Inputs should contain aligned trial/path scores. For a single model this is
    only a coarse warning metric; it becomes more meaningful when every tried
    variant is logged.
    """
    is_values = np.asarray(list(in_sample_scores), dtype=float)
    oos_values = np.asarray(list(out_of_sample_scores), dtype=float)
    mask = np.isfinite(is_values) & np.isfinite(oos_values)
    is_values = is_values[mask]
    oos_values = oos_values[mask]
    if len(is_values) == 0:
        return {"pbo": None, "n_trials": 0, "warning": "No valid trial scores."}
    best_idx = int(np.argmax(is_values))
    oos_median = float(np.median(oos_values))
    overfit = bool(oos_values[best_idx] < oos_median)
    percentile = float(np.mean(oos_values <= oos_values[best_idx]))
    return {
        "pbo": 1.0 if overfit else 0.0,
        "n_trials": int(len(is_values)),
        "selected_in_sample_score": round(float(is_values[best_idx]), 6),
        "selected_out_of_sample_score": round(float(oos_values[best_idx]), 6),
        "out_of_sample_median": round(oos_median, 6),
        "selected_oos_percentile": round(percentile, 6),
        "method": "single_selection_oos_median",
    }


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))
