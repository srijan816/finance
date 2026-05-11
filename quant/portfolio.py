"""Portfolio construction utilities for research workflows."""
from __future__ import annotations

from typing import Dict, Sequence

import numpy as np

from quant.metrics import summarize_performance
from quant.research_status import research_grade_status
from quant.strategies import prices_to_returns


def optimize_portfolio(
    tickers: Sequence[str],
    start: str,
    end: str,
    method: str = "min_variance",
    benchmark: str = "SPY",
    risk_free_rate: float = 0.0,
) -> Dict:
    """Build a long-only portfolio from historical daily returns."""
    from quant.data import fetch_bars

    returns_by_ticker = {}
    for ticker in tickers:
        bars = fetch_bars(ticker, start, end)
        if len(bars) < 20:
            return {"error": f"Insufficient data for {ticker}: {len(bars)} bars"}
        returns_by_ticker[ticker] = prices_to_returns([row[4] for row in bars])

    names, matrix = _align_returns(returns_by_ticker)
    if matrix.shape[0] < 2:
        return {"error": "Not enough overlapping returns"}

    weights = weights_for_method(matrix, method)
    portfolio_returns = matrix @ weights

    benchmark_returns = None
    if benchmark:
        try:
            benchmark_bars = fetch_bars(benchmark, start, end)
            benchmark_returns = prices_to_returns([row[4] for row in benchmark_bars])
            benchmark_returns = benchmark_returns[-len(portfolio_returns):]
        except Exception:
            benchmark_returns = None

    metrics = summarize_performance(portfolio_returns, benchmark_returns, risk_free_rate)
    return {
        "method": method,
        "start": start,
        "end": end,
        "benchmark": benchmark if benchmark_returns is not None else None,
        "weights": {name: round(float(weight), 4) for name, weight in zip(names, weights)},
        "metrics": {key: round(float(value), 4) for key, value in metrics.items()},
        "assumptions": {
            "long_only": True,
            "rebalance": "single static allocation estimated over the full sample",
            "covariance": "sample covariance of daily returns",
        },
        "research_grade_status": research_grade_status(
            data_source="yfinance",
            universe_name="user_supplied_tickers",
            validation_method="static_full_sample_optimizer",
            has_risk_optimizer=True,
            feature_sources=["price_volume"],
            notes=[
                "This optimizer uses covariance, but it is static/full-sample and not integrated into V2 recommendations.",
            ],
        ),
    }


def weights_for_method(returns_matrix: np.ndarray, method: str) -> np.ndarray:
    name = method.lower().replace("-", "_")
    if name in {"equal", "equal_weight"}:
        return _equal_weights(returns_matrix)
    if name in {"inverse_vol", "risk_parity"}:
        return _inverse_vol_weights(returns_matrix)
    if name in {"min_variance", "minimum_variance", "min_vol"}:
        return _min_variance_weights(returns_matrix)
    if name in {"max_sharpe", "tangency"}:
        return _max_sharpe_weights(returns_matrix)
    raise ValueError(f"Unknown portfolio method: {method}")


def _align_returns(returns_by_ticker: Dict[str, np.ndarray]) -> tuple[list[str], np.ndarray]:
    names = list(returns_by_ticker)
    n = min(len(returns_by_ticker[name]) for name in names)
    matrix = np.column_stack([returns_by_ticker[name][-n:] for name in names])
    matrix = matrix[np.all(np.isfinite(matrix), axis=1)]
    return names, matrix


def _equal_weights(returns_matrix: np.ndarray) -> np.ndarray:
    n = returns_matrix.shape[1]
    return np.repeat(1 / n, n)


def _inverse_vol_weights(returns_matrix: np.ndarray) -> np.ndarray:
    vol = np.std(returns_matrix, axis=0, ddof=1)
    inv = np.divide(1.0, vol, out=np.zeros_like(vol), where=vol > 0)
    if inv.sum() == 0:
        return _equal_weights(returns_matrix)
    return inv / inv.sum()


def _min_variance_weights(returns_matrix: np.ndarray) -> np.ndarray:
    cov = np.cov(returns_matrix, rowvar=False)
    ones = np.ones(cov.shape[0])
    raw = np.linalg.pinv(cov) @ ones
    return _long_only_normalize(raw)


def _max_sharpe_weights(returns_matrix: np.ndarray) -> np.ndarray:
    mu = np.mean(returns_matrix, axis=0)
    cov = np.cov(returns_matrix, rowvar=False)
    raw = np.linalg.pinv(cov) @ mu
    return _long_only_normalize(raw)


def _long_only_normalize(raw: np.ndarray) -> np.ndarray:
    clipped = np.clip(raw, 0, None)
    if clipped.sum() == 0:
        return np.repeat(1 / len(raw), len(raw))
    return clipped / clipped.sum()
