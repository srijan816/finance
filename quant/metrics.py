"""Research-grade performance and risk metrics."""
from __future__ import annotations

from typing import Dict, Iterable

import numpy as np

TRADING_DAYS = 252


def as_array(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr)]


def annualized_return(returns: Iterable[float], periods: int = TRADING_DAYS) -> float:
    r = as_array(returns)
    if len(r) == 0:
        return 0.0
    total = float(np.prod(1 + r))
    if total <= 0:
        return -1.0
    return total ** (periods / len(r)) - 1


def annualized_volatility(returns: Iterable[float], periods: int = TRADING_DAYS) -> float:
    r = as_array(returns)
    if len(r) < 2:
        return 0.0
    return float(np.std(r, ddof=1) * np.sqrt(periods))


def sharpe_ratio(returns: Iterable[float], risk_free_rate: float = 0.0, periods: int = TRADING_DAYS) -> float:
    r = as_array(returns)
    if len(r) < 2:
        return 0.0
    excess = r - risk_free_rate / periods
    vol = np.std(excess, ddof=1)
    if vol == 0:
        return 0.0
    return float(np.mean(excess) / vol * np.sqrt(periods))


def sortino_ratio(returns: Iterable[float], risk_free_rate: float = 0.0, periods: int = TRADING_DAYS) -> float:
    r = as_array(returns)
    if len(r) < 2:
        return 0.0
    excess = r - risk_free_rate / periods
    downside = excess[excess < 0]
    if len(downside) == 0:
        return 0.0
    downside_dev = np.std(downside, ddof=1) if len(downside) > 1 else abs(float(downside[0]))
    if downside_dev == 0:
        return 0.0
    return float(np.mean(excess) / downside_dev * np.sqrt(periods))


def equity_curve(returns: Iterable[float], initial_capital: float = 1.0) -> np.ndarray:
    r = as_array(returns)
    if len(r) == 0:
        return np.asarray([initial_capital], dtype=float)
    return initial_capital * np.cumprod(1 + r)


def max_drawdown(returns: Iterable[float]) -> float:
    curve = equity_curve(returns)
    peaks = np.maximum.accumulate(curve)
    drawdowns = curve / peaks - 1
    return float(drawdowns.min()) if len(drawdowns) else 0.0


def calmar_ratio(returns: Iterable[float]) -> float:
    ann = annualized_return(returns)
    dd = abs(max_drawdown(returns))
    if dd == 0:
        return 0.0
    return float(ann / dd)


def value_at_risk(returns: Iterable[float], confidence: float = 0.95) -> float:
    r = as_array(returns)
    if len(r) == 0:
        return 0.0
    return float(np.quantile(r, 1 - confidence))


def conditional_value_at_risk(returns: Iterable[float], confidence: float = 0.95) -> float:
    r = as_array(returns)
    if len(r) == 0:
        return 0.0
    threshold = value_at_risk(r, confidence)
    tail = r[r <= threshold]
    return float(tail.mean()) if len(tail) else threshold


def beta(returns: Iterable[float], benchmark_returns: Iterable[float]) -> float:
    r = as_array(returns)
    b = as_array(benchmark_returns)
    n = min(len(r), len(b))
    if n < 2:
        return 0.0
    r = r[-n:]
    b = b[-n:]
    variance = float(np.var(b, ddof=1))
    if variance == 0:
        return 0.0
    return float(np.cov(r, b, ddof=1)[0, 1] / variance)


def alpha(
    returns: Iterable[float],
    benchmark_returns: Iterable[float],
    risk_free_rate: float = 0.0,
    periods: int = TRADING_DAYS,
) -> float:
    r = as_array(returns)
    b = as_array(benchmark_returns)
    n = min(len(r), len(b))
    if n == 0:
        return 0.0
    r = r[-n:]
    b = b[-n:]
    ann_r = annualized_return(r, periods)
    ann_b = annualized_return(b, periods)
    return float(ann_r - (risk_free_rate + beta(r, b) * (ann_b - risk_free_rate)))


def information_ratio(returns: Iterable[float], benchmark_returns: Iterable[float], periods: int = TRADING_DAYS) -> float:
    r = as_array(returns)
    b = as_array(benchmark_returns)
    n = min(len(r), len(b))
    if n < 2:
        return 0.0
    active = r[-n:] - b[-n:]
    tracking_error = np.std(active, ddof=1)
    if tracking_error == 0:
        return 0.0
    return float(np.mean(active) / tracking_error * np.sqrt(periods))


def hit_rate(returns: Iterable[float]) -> float:
    r = as_array(returns)
    if len(r) == 0:
        return 0.0
    return float(np.mean(r > 0))


def summarize_performance(
    returns: Iterable[float],
    benchmark_returns: Iterable[float] | None = None,
    risk_free_rate: float = 0.0,
) -> Dict[str, float]:
    r = as_array(returns)
    summary = {
        "total_return": float(np.prod(1 + r) - 1) if len(r) else 0.0,
        "annual_return": annualized_return(r),
        "annual_volatility": annualized_volatility(r),
        "sharpe": sharpe_ratio(r, risk_free_rate),
        "sortino": sortino_ratio(r, risk_free_rate),
        "calmar": calmar_ratio(r),
        "max_dd": max_drawdown(r),
        "win_rate": hit_rate(r),
        "var_95": value_at_risk(r),
        "cvar_95": conditional_value_at_risk(r),
    }
    if benchmark_returns is not None:
        b = as_array(benchmark_returns)
        summary.update({
            "benchmark_total_return": float(np.prod(1 + b) - 1) if len(b) else 0.0,
            "alpha": alpha(r, b, risk_free_rate),
            "beta": beta(r, b),
            "information_ratio": information_ratio(r, b),
        })
    return summary
