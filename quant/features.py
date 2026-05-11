"""Cross-sectional feature transformations."""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd


def add_cross_sectional_features(
    frame: pd.DataFrame,
    feature_cols: Sequence[str],
    date_col: str = "sample_date",
    sector_col: str | None = None,
    winsor_quantile: float = 0.01,
) -> pd.DataFrame:
    """Add per-date z-score, rank, and optional sector-neutral z-score columns."""
    out = frame.copy()
    out[date_col] = pd.to_datetime(out[date_col])
    for column in feature_cols:
        clipped = out.groupby(date_col, group_keys=False)[column].transform(
            lambda values: _winsorize(values.astype(float), winsor_quantile)
        )
        out[f"{column}_xsec_z"] = clipped.groupby(out[date_col]).transform(_zscore)
        out[f"{column}_xsec_rank"] = clipped.groupby(out[date_col]).rank(pct=True)
        if sector_col and sector_col in out:
            out[f"{column}_sector_z"] = clipped.groupby([out[date_col], out[sector_col]]).transform(_zscore)
    return out


def residualize_against_group_return(
    frame: pd.DataFrame,
    return_col: str,
    group_return_col: str,
    output_col: str = "residual_return",
) -> pd.DataFrame:
    """Add residual return after removing same-date group return."""
    out = frame.copy()
    out[output_col] = out[return_col].astype(float) - out[group_return_col].astype(float)
    return out


def _winsorize(values: pd.Series, quantile: float) -> pd.Series:
    if len(values.dropna()) < 3 or quantile <= 0:
        return values
    lower = values.quantile(quantile)
    upper = values.quantile(1 - quantile)
    return values.clip(lower, upper)


def _zscore(values: pd.Series) -> pd.Series:
    std = values.std(ddof=0)
    if not np.isfinite(std) or std <= 1e-12:
        return pd.Series(0.0, index=values.index)
    return (values - values.mean()) / std
