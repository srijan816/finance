"""Purged and embargoed validation helpers for overlapping forward labels."""
from __future__ import annotations

from itertools import combinations
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from quant.backtest_diagnostics import deflated_sharpe_probability, probability_of_backtest_overfitting


def default_embargo_days(horizon: int) -> int:
    """Conservative default from the audit plan."""
    return max(10, int(np.ceil(horizon * 0.15)))


def ensure_label_intervals(samples: pd.DataFrame, horizon: int, date_col: str = "sample_date") -> pd.DataFrame:
    """Ensure samples carry label start/end dates for purge logic."""
    out = samples.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    if "label_start_date" not in out:
        out["label_start_date"] = out[date_col]
    else:
        out["label_start_date"] = pd.to_datetime(out["label_start_date"])
    if "label_end_date" not in out:
        out["label_end_date"] = out[date_col] + pd.to_timedelta(horizon, unit="D")
    else:
        out["label_end_date"] = pd.to_datetime(out["label_end_date"])
    return out


def purge_and_embargo_train(
    train: pd.DataFrame,
    test: pd.DataFrame,
    embargo_days: int,
    date_col: str = "sample_date",
) -> pd.DataFrame:
    """Drop training rows whose label windows overlap test labels or embargo."""
    if train.empty or test.empty:
        return train.copy()
    train = ensure_label_intervals(train, 1, date_col=date_col)
    test = ensure_label_intervals(test, 1, date_col=date_col)
    keep = pd.Series(True, index=train.index)
    for _, test_row in test.iterrows():
        test_start = test_row["label_start_date"]
        test_end = test_row["label_end_date"]
        overlap = (train["label_start_date"] <= test_end) & (train["label_end_date"] >= test_start)
        embargo_end = test_end + pd.to_timedelta(embargo_days, unit="D")
        embargo = (train[date_col] > test_end) & (train[date_col] <= embargo_end)
        keep &= ~(overlap | embargo)
    return train.loc[keep].copy()


def purged_walk_forward_splits(
    samples: pd.DataFrame,
    horizon: int,
    min_train_samples: int = 250,
    test_window_samples: int = 80,
    embargo_days: int | None = None,
    date_col: str = "sample_date",
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    ordered = ensure_label_intervals(samples, horizon, date_col=date_col).sort_values(date_col).reset_index(drop=True)
    embargo_days = default_embargo_days(horizon) if embargo_days is None else int(embargo_days)
    splits = []
    start = min_train_samples
    while start + test_window_samples <= len(ordered):
        raw_train = ordered.iloc[:start]
        test = ordered.iloc[start:start + test_window_samples]
        train = purge_and_embargo_train(raw_train, test, embargo_days, date_col=date_col)
        if len(train) > 0 and len(test) > 0:
            splits.append((train, test))
        start += test_window_samples
    return splits


def combinatorial_purged_splits(
    samples: pd.DataFrame,
    horizon: int,
    n_groups: int = 6,
    k_test_groups: int = 2,
    embargo_days: int | None = None,
    date_col: str = "sample_date",
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    ordered = ensure_label_intervals(samples, horizon, date_col=date_col).sort_values(date_col).reset_index(drop=True)
    if n_groups < 2 or k_test_groups < 1 or k_test_groups >= n_groups:
        raise ValueError("Require 1 <= k_test_groups < n_groups")
    embargo_days = default_embargo_days(horizon) if embargo_days is None else int(embargo_days)
    groups = np.array_split(np.arange(len(ordered)), n_groups)
    splits = []
    for test_group_ids in combinations(range(n_groups), k_test_groups):
        test_idx = np.concatenate([groups[i] for i in test_group_ids])
        raw_train_idx = np.setdiff1d(np.arange(len(ordered)), test_idx)
        test = ordered.iloc[test_idx].sort_values(date_col)
        raw_train = ordered.iloc[raw_train_idx].sort_values(date_col)
        train = purge_and_embargo_train(raw_train, test, embargo_days, date_col=date_col)
        if len(train) > 0 and len(test) > 0:
            splits.append((train, test))
    return splits


def score_prediction_folds(
    folds: Iterable[tuple[pd.DataFrame, pd.DataFrame]],
    fit_predict,
    feature_cols: Sequence[str],
    target_col: str = "forward_active_return",
) -> dict:
    """Score folds with a caller-supplied function returning predictions."""
    results = []
    is_scores = []
    oos_scores = []
    for train, test in folds:
        predictions = np.asarray(fit_predict(train, test, feature_cols), dtype=float)
        actual = test[target_col].to_numpy(dtype=float)
        if len(predictions) != len(actual):
            raise ValueError("fit_predict must return one prediction per test row")
        rank_ic = _safe_corr(pd.Series(predictions).rank().to_numpy(), pd.Series(actual).rank().to_numpy())
        top_cut = np.quantile(predictions, 0.8)
        top_actual = actual[predictions >= top_cut]
        train_actual = train[target_col].to_numpy(dtype=float)
        is_scores.append(float(np.mean(train_actual) / (np.std(train_actual) + 1e-12)))
        oos_scores.append(rank_ic)
        results.append({
            "test_start": str(pd.to_datetime(test["sample_date"].iloc[0]).date()),
            "test_end": str(pd.to_datetime(test["sample_date"].iloc[-1]).date()),
            "train_samples_after_purge": int(len(train)),
            "test_samples": int(len(test)),
            "rank_ic": round(rank_ic, 6),
            "top_quintile_avg_return": round(float(np.mean(top_actual)) if len(top_actual) else 0.0, 6),
            "all_avg_return": round(float(np.mean(actual)) if len(actual) else 0.0, 6),
        })
    ic_values = [row["rank_ic"] for row in results]
    return {
        "n_folds": len(results),
        "avg_rank_ic": round(float(np.mean(ic_values)) if ic_values else 0.0, 6),
        "median_rank_ic": round(float(np.median(ic_values)) if ic_values else 0.0, 6),
        "folds": results,
        "pbo": probability_of_backtest_overfitting(is_scores, oos_scores),
        "dsr": deflated_sharpe_probability(
            sharpe=float(np.mean(ic_values) / (np.std(ic_values, ddof=1) + 1e-12)) if len(ic_values) > 1 else 0.0,
            n_observations=max(len(ic_values), 1),
            n_trials=max(len(results), 1),
        ),
    }


def _safe_corr(left: np.ndarray, right: np.ndarray) -> float:
    if len(left) < 2 or np.std(left) <= 1e-12 or np.std(right) <= 1e-12:
        return 0.0
    value = float(np.corrcoef(left, right)[0, 1])
    return 0.0 if not np.isfinite(value) else value
