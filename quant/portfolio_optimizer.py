"""Risk-aware allocation from alpha recommendations."""
from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from quant.allocation import SECTOR_CAPS, SECTOR_MAP
from quant.research_status import research_grade_status


def optimize_recommendation_portfolio(
    recommendations: Sequence[dict],
    returns_by_ticker: Mapping[str, Sequence[float]],
    capital: float,
    current_weights: Mapping[str, float] | None = None,
    max_position_pct: float = 0.18,
    cash_reserve_pct: float = 0.10,
    risk_aversion: float = 4.0,
    turnover_penalty: float = 0.25,
) -> dict:
    """Convert alpha scores into capped, covariance-aware long-only weights."""
    candidates = [row for row in recommendations if row.get("predicted_63d_active_return", 0) > 0]
    tickers = [row["ticker"] for row in candidates if row["ticker"] in returns_by_ticker]
    if not tickers or capital <= 0:
        return _empty(capital)

    matrix = _aligned_returns([returns_by_ticker[ticker] for ticker in tickers])
    if matrix.shape[0] < 2:
        return _empty(capital, warning="Not enough overlapping returns for risk optimization.")
    mu = np.asarray([max(float(row.get("predicted_63d_active_return", 0)), 0.0) for row in candidates if row["ticker"] in tickers])
    cov = np.cov(matrix, rowvar=False)
    vol = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    raw = np.maximum(mu / (risk_aversion * vol), 0.0)
    if raw.sum() <= 1e-12:
        raw = 1 / vol
    weights = raw / raw.sum() * (1 - cash_reserve_pct)
    weights = _apply_turnover_penalty(tickers, weights, current_weights or {}, turnover_penalty)
    weights = _apply_caps(tickers, weights, max_position_pct)
    allocations = []
    for ticker, weight in zip(tickers, weights):
        if weight <= 1e-8:
            continue
        row = next(item for item in candidates if item["ticker"] == ticker)
        allocations.append({
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "unknown"),
            "weight": round(float(weight), 6),
            "allocation": round(float(weight * capital), 2),
            "predicted_63d_active_return": row.get("predicted_63d_active_return"),
            "volatility_estimate": round(float(vol[tickers.index(ticker)]), 6),
        })
    invested = sum(item["allocation"] for item in allocations)
    portfolio_var = float(weights @ cov @ weights) if len(weights) == cov.shape[0] else 0.0
    return {
        "capital": round(capital, 2),
        "allocations": allocations,
        "cash": round(capital - invested, 2),
        "risk": {
            "portfolio_daily_vol_estimate": round(float(np.sqrt(max(portfolio_var, 0.0))), 6),
            "portfolio_annual_vol_estimate": round(float(np.sqrt(max(portfolio_var, 0.0)) * np.sqrt(252)), 6),
            "covariance": "sample covariance of supplied aligned returns",
        },
        "policy": {
            "max_position_pct": max_position_pct,
            "cash_reserve_pct": cash_reserve_pct,
            "risk_aversion": risk_aversion,
            "turnover_penalty": turnover_penalty,
            "sector_caps": SECTOR_CAPS,
        },
        "research_grade_status": research_grade_status(
            data_source="yfinance",
            universe_name="recommendation_candidates",
            validation_method="risk_optimizer_allocation_only",
            has_risk_optimizer=True,
            feature_sources=["price_volume"],
            notes=["Risk optimizer is present, but production status still requires PIT data, purged validation, and execution shortfall."],
        ),
    }


def _empty(capital: float, warning: str = "No eligible candidates.") -> dict:
    return {"capital": round(capital, 2), "allocations": [], "cash": round(capital, 2), "warning": warning}


def _aligned_returns(series: Sequence[Sequence[float]]) -> np.ndarray:
    n = min(len(values) for values in series)
    matrix = np.column_stack([np.asarray(values, dtype=float)[-n:] for values in series])
    return matrix[np.all(np.isfinite(matrix), axis=1)]


def _apply_turnover_penalty(tickers: list[str], weights: np.ndarray, current: Mapping[str, float], penalty: float) -> np.ndarray:
    if penalty <= 0:
        return weights
    current_vec = np.asarray([max(float(current.get(ticker, 0.0)), 0.0) for ticker in tickers])
    blended = (1 - penalty) * weights + penalty * current_vec
    total = blended.sum()
    return weights if total <= 1e-12 else blended / total * weights.sum()


def _apply_caps(tickers: list[str], weights: np.ndarray, max_position_pct: float) -> np.ndarray:
    capped = np.minimum(weights, max_position_pct)
    sector_used: dict[str, float] = {}
    for idx, ticker in enumerate(tickers):
        sector = SECTOR_MAP.get(ticker, "unknown")
        cap = SECTOR_CAPS.get(sector, SECTOR_CAPS["unknown"])
        remaining = max(cap - sector_used.get(sector, 0.0), 0.0)
        capped[idx] = min(capped[idx], remaining)
        sector_used[sector] = sector_used.get(sector, 0.0) + capped[idx]
    total = capped.sum()
    target = min(weights.sum(), 1.0)
    return capped if total <= 1e-12 else capped / total * min(total, target)
