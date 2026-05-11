"""Alphalens-style factor diagnostics for model scores."""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def factor_diagnostics(
    factor_data: pd.DataFrame,
    factor_col: str = "factor",
    forward_return_col: str = "forward_return",
    date_col: str = "date",
    asset_col: str = "asset",
    group_col: str | None = None,
    quantiles: int = 5,
) -> dict:
    """Compute IC, quantile spread, turnover, and optional group diagnostics."""
    data = factor_data.copy()
    data[date_col] = pd.to_datetime(data[date_col])
    data = data.dropna(subset=[factor_col, forward_return_col, date_col, asset_col])
    if data.empty:
        return {"n_observations": 0, "warning": "No valid factor rows."}

    data["factor_quantile"] = data.groupby(date_col)[factor_col].transform(
        lambda values: _quantile_labels(values, quantiles)
    )
    ic_by_date = pd.Series({
        key: _spearman(group[factor_col], group[forward_return_col])
        for key, group in data.groupby(date_col)
    })
    mean_by_quantile = data.groupby("factor_quantile")[forward_return_col].mean().to_dict()
    top_q = max(mean_by_quantile)
    bottom_q = min(mean_by_quantile)
    turnover = _quantile_turnover(data, date_col, asset_col, "factor_quantile", top_q)
    rank_autocorr = _rank_autocorr(data, date_col, asset_col, factor_col)
    result = {
        "n_observations": int(len(data)),
        "n_dates": int(data[date_col].nunique()),
        "mean_ic": round(float(ic_by_date.mean()), 6),
        "median_ic": round(float(ic_by_date.median()), 6),
        "ic_by_date": {str(key.date()): round(float(value), 6) for key, value in ic_by_date.items()},
        "mean_return_by_quantile": {int(key): round(float(value), 6) for key, value in mean_by_quantile.items()},
        "top_bottom_spread": round(float(mean_by_quantile[top_q] - mean_by_quantile[bottom_q]), 6),
        "top_quantile_turnover": round(float(turnover), 6),
        "factor_rank_autocorrelation": round(float(rank_autocorr), 6),
    }
    if group_col and group_col in data:
        group_ic = pd.Series({
            key: _spearman(group[factor_col], group[forward_return_col])
            for key, group in data.groupby(group_col)
        })
        result["ic_by_group"] = {str(key): round(float(value), 6) for key, value in group_ic.items()}
    return result


def _quantile_labels(values: pd.Series, quantiles: int) -> pd.Series:
    ranks = values.rank(method="first")
    try:
        return pd.qcut(ranks, quantiles, labels=False, duplicates="drop") + 1
    except ValueError:
        return pd.Series(1, index=values.index)


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    left_rank = pd.Series(left).rank().to_numpy()
    right_rank = pd.Series(right).rank().to_numpy()
    if len(left_rank) < 2 or np.std(left_rank) <= 1e-12 or np.std(right_rank) <= 1e-12:
        return 0.0
    value = float(np.corrcoef(left_rank, right_rank)[0, 1])
    return 0.0 if not np.isfinite(value) else value


def _quantile_turnover(data: pd.DataFrame, date_col: str, asset_col: str, quantile_col: str, quantile: int) -> float:
    previous = None
    turnovers = []
    for _, group in data.sort_values(date_col).groupby(date_col):
        current = set(group.loc[group[quantile_col] == quantile, asset_col])
        if previous is not None and current:
            turnovers.append(1 - len(current & previous) / len(current))
        previous = current
    return float(np.mean(turnovers)) if turnovers else 0.0


def _rank_autocorr(data: pd.DataFrame, date_col: str, asset_col: str, factor_col: str) -> float:
    ranks = data.pivot_table(index=date_col, columns=asset_col, values=factor_col, aggfunc="mean").rank(axis=1)
    cors = []
    for i in range(1, len(ranks)):
        joined = pd.concat([ranks.iloc[i - 1], ranks.iloc[i]], axis=1).dropna()
        if len(joined) > 1:
            cors.append(_spearman(joined.iloc[:, 0], joined.iloc[:, 1]))
    return float(np.mean(cors)) if cors else 0.0
