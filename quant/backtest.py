"""Lookahead-safe daily backtest harness with explicit assumptions."""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

from quant.metrics import summarize_performance
from quant.research_status import research_grade_status
from quant.strategies import prices_to_returns, signal_for_strategy


def run_backtest(
    tickers: Sequence[str],
    start: str,
    end: str,
    strategy: str = "sma_cross",
    benchmark: str = "SPY",
    initial_capital: float = 100_000.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 2.0,
    risk_free_rate: float = 0.0,
) -> List[Dict]:
    """Run a daily long/cash strategy backtest for each ticker."""
    from quant.data import fetch_bars

    benchmark_returns = _safe_benchmark_returns(benchmark, start, end, fetch_bars)
    results = []
    for ticker in tickers:
        try:
            bars = fetch_bars(ticker, start, end)
            result = backtest_bars(
                ticker=ticker,
                bars=bars,
                strategy=strategy,
                benchmark_returns=benchmark_returns,
                initial_capital=initial_capital,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
                risk_free_rate=risk_free_rate,
                benchmark=benchmark,
            )
            results.append(result)
        except Exception as exc:
            results.append({"ticker": ticker, "error": str(exc)})
    return results


def backtest_bars(
    ticker: str,
    bars: Sequence[tuple],
    strategy: str = "sma_cross",
    benchmark_returns: Sequence[float] | None = None,
    initial_capital: float = 100_000.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 2.0,
    risk_free_rate: float = 0.0,
    benchmark: str = "SPY",
    warmup_bars: int = 0,
) -> Dict:
    """Backtest pre-fetched OHLCV bars, useful for tests and validation windows."""
    if not bars:
        return {"ticker": ticker, "error": "No data fetched"}
    if len(bars) < 20:
        return {"ticker": ticker, "error": f"Insufficient data: {len(bars)} bars"}

    dates = [row[0] for row in bars]
    closes = np.asarray([row[4] for row in bars], dtype=float)
    asset_returns = prices_to_returns(closes)
    if len(asset_returns) == 0 or np.std(asset_returns) == 0:
        return {"ticker": ticker, "error": "No price variance"}

    raw_signal = signal_for_strategy(strategy, closes)
    # Use yesterday's signal for today's return to avoid lookahead bias.
    positions = raw_signal[:-1]
    strategy_returns, turnover_series = _apply_costs(asset_returns, positions, commission_bps, slippage_bps)
    eval_start = max(warmup_bars - 1, 0)
    eval_returns = strategy_returns[eval_start:]
    eval_positions = positions[eval_start:]
    eval_turnover_series = turnover_series[eval_start:]
    bench = _align_benchmark(benchmark_returns, len(strategy_returns))
    eval_bench = None if bench is None else bench[-len(eval_returns):]
    metrics = summarize_performance(eval_returns, eval_bench, risk_free_rate)

    final_equity = float(initial_capital * np.prod(1 + eval_returns))
    exposure = float(np.mean(eval_positions != 0)) if len(eval_positions) else 0.0
    trades = int(np.sum(eval_turnover_series > 0))
    turnover = float(np.sum(eval_turnover_series) / len(eval_turnover_series)) if len(eval_turnover_series) else 0.0
    start_date = dates[eval_start] if eval_start < len(dates) else dates[0]

    return {
        "ticker": ticker,
        "strategy": strategy,
        "benchmark": benchmark if bench is not None else None,
        "start": start_date,
        "end": dates[-1],
        "n_bars": len(eval_returns) + 1,
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return": round(metrics["total_return"] * 100, 2),
        "annual_return": round(metrics["annual_return"] * 100, 2),
        "annual_volatility": round(metrics["annual_volatility"] * 100, 2),
        "sharpe": round(metrics["sharpe"], 2),
        "sortino": round(metrics["sortino"], 2),
        "calmar": round(metrics["calmar"], 2),
        "max_dd": round(abs(metrics["max_dd"]) * 100, 1),
        "win_rate": round(metrics["win_rate"] * 100, 1),
        "var_95": round(metrics["var_95"] * 100, 2),
        "cvar_95": round(metrics["cvar_95"] * 100, 2),
        "alpha": round(metrics.get("alpha", 0.0) * 100, 2),
        "beta": round(metrics.get("beta", 0.0), 2),
        "information_ratio": round(metrics.get("information_ratio", 0.0), 2),
        "benchmark_total_return": round(metrics.get("benchmark_total_return", 0.0) * 100, 2),
        "exposure": round(exposure * 100, 1),
        "turnover": round(turnover * 100, 1),
        "trades": trades,
        "assumptions": {
            "signal_lag": "Signals are lagged one bar before applying returns.",
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "risk_free_rate": risk_free_rate,
            "warmup_bars": warmup_bars,
        },
        "research_grade_status": research_grade_status(
            data_source="yfinance",
            universe_name=ticker,
            validation_method="single_ticker_lagged_signal_backtest",
            feature_sources=["price_volume"],
            notes=[
                "Signals are lagged one bar, but the ticker set is not a survivorship-bias-free historical universe.",
            ],
        ),
    }


def _apply_costs(
    asset_returns: np.ndarray,
    positions: np.ndarray,
    commission_bps: float,
    slippage_bps: float,
) -> tuple[np.ndarray, np.ndarray]:
    positions = np.asarray(positions, dtype=float)
    gross = positions * asset_returns
    position_changes = np.abs(np.diff(np.insert(positions, 0, 0.0)))
    cost_rate = (commission_bps + slippage_bps) / 10_000
    costs = position_changes * cost_rate
    net = gross - costs
    return net, position_changes


def _safe_benchmark_returns(benchmark: str, start: str, end: str, fetcher) -> np.ndarray | None:
    if not benchmark:
        return None
    try:
        bars = fetcher(benchmark, start, end)
        closes = [row[4] for row in bars]
        return prices_to_returns(closes)
    except Exception:
        return None


def _align_benchmark(benchmark_returns: Sequence[float] | None, target_len: int) -> np.ndarray | None:
    if benchmark_returns is None:
        return None
    bench = np.asarray(list(benchmark_returns), dtype=float)
    if len(bench) == 0:
        return None
    n = min(len(bench), target_len)
    return bench[-n:]
