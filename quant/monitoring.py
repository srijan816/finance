"""Live/paper signal monitoring utilities."""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def monitoring_snapshot(
    records: Sequence[dict],
    prediction_col: str = "prediction",
    realized_col: str = "realized_return",
    date_col: str = "date",
    window: int = 60,
) -> dict:
    """Compute rolling IC and calibration once realized labels are available."""
    if not records:
        return {"n_records": 0, "warning": "No monitoring records."}
    frame = pd.DataFrame(records).dropna(subset=[prediction_col, realized_col, date_col])
    if frame.empty:
        return {"n_records": 0, "warning": "No realized monitoring records."}
    frame[date_col] = pd.to_datetime(frame[date_col])
    by_date = pd.Series({
        key: _spearman(group[prediction_col], group[realized_col])
        for key, group in frame.groupby(date_col)
    }).sort_index()
    rolling = by_date.rolling(min(window, len(by_date)), min_periods=1).mean()
    return {
        "n_records": int(len(frame)),
        "n_dates": int(frame[date_col].nunique()),
        "mean_ic": round(float(by_date.mean()), 6),
        "latest_rolling_ic": round(float(rolling.iloc[-1]), 6),
        "window": window,
        "calibration": calibration_bins(frame[prediction_col], frame[realized_col]),
    }


def calibration_bins(predictions: Sequence[float], realized: Sequence[float], bins: int = 5) -> list[dict]:
    frame = pd.DataFrame({"prediction": predictions, "realized": realized}).dropna()
    if frame.empty:
        return []
    frame["bin"] = pd.qcut(frame["prediction"].rank(method="first"), bins, labels=False, duplicates="drop") + 1
    rows = []
    for bucket, group in frame.groupby("bin"):
        rows.append({
            "bin": int(bucket),
            "n": int(len(group)),
            "avg_prediction": round(float(group["prediction"].mean()), 6),
            "avg_realized": round(float(group["realized"].mean()), 6),
        })
    return rows


def _spearman(left, right) -> float:
    left_rank = pd.Series(left).rank().to_numpy()
    right_rank = pd.Series(right).rank().to_numpy()
    if len(left_rank) < 2 or np.std(left_rank) <= 1e-12 or np.std(right_rank) <= 1e-12:
        return 0.0
    value = float(np.corrcoef(left_rank, right_rank)[0, 1])
    return 0.0 if not np.isfinite(value) else value
