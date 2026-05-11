"""Walk-forward validation utilities for research strategies."""
from __future__ import annotations

from typing import Dict, List, Sequence

from quant.backtest import backtest_bars
from quant.research_status import research_grade_status


def walk_forward_validate(
    ticker: str,
    start: str,
    end: str,
    strategy: str = "sma_cross",
    train_bars: int = 252,
    test_bars: int = 63,
    benchmark: str = "SPY",
    commission_bps: float = 0.0,
    slippage_bps: float = 2.0,
) -> Dict:
    """Evaluate a strategy across rolling out-of-sample windows."""
    from quant.data import fetch_bars
    from quant.strategies import prices_to_returns

    bars = fetch_bars(ticker, start, end)
    if len(bars) < train_bars + test_bars:
        return {
            "ticker": ticker,
            "error": f"Need at least {train_bars + test_bars} bars, got {len(bars)}",
        }

    benchmark_returns = None
    if benchmark:
        try:
            benchmark_bars = fetch_bars(benchmark, start, end)
            benchmark_returns = prices_to_returns([row[4] for row in benchmark_bars])
        except Exception:
            benchmark_returns = None

    windows = []
    cursor = train_bars
    while cursor + test_bars <= len(bars):
        window = bars[cursor - train_bars: cursor + test_bars]
        test_window = bars[cursor: cursor + test_bars]
        result = backtest_bars(
            ticker=ticker,
            bars=window,
            strategy=strategy,
            benchmark_returns=_slice_benchmark(benchmark_returns, cursor - train_bars, train_bars + test_bars),
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            benchmark=benchmark,
            warmup_bars=train_bars,
        )
        result["train_start"] = bars[cursor - train_bars][0]
        result["train_end"] = bars[cursor - 1][0]
        result["test_start"] = test_window[0][0]
        result["test_end"] = test_window[-1][0]
        windows.append(result)
        cursor += test_bars

    return {
        "ticker": ticker,
        "strategy": strategy,
        "benchmark": benchmark,
        "train_bars": train_bars,
        "test_bars": test_bars,
        "windows": windows,
        "summary": summarize_windows(windows),
        "research_grade_status": research_grade_status(
            data_source="yfinance",
            universe_name=ticker,
            validation_method="rolling_walk_forward_unpurged",
            feature_sources=["price_volume"],
            notes=[
                "This validation is rolling out-of-sample, but it is not purged/embargoed CPCV.",
            ],
        ),
    }


def summarize_windows(windows: Sequence[Dict]) -> Dict:
    valid = [w for w in windows if "error" not in w]
    if not valid:
        return {"n_windows": len(windows), "n_valid": 0}
    return {
        "n_windows": len(windows),
        "n_valid": len(valid),
        "median_sharpe": _median([w["sharpe"] for w in valid]),
        "median_total_return": _median([w["total_return"] for w in valid]),
        "worst_drawdown": max(w["max_dd"] for w in valid),
        "positive_windows": round(100 * sum(w["total_return"] > 0 for w in valid) / len(valid), 1),
    }


def _slice_benchmark(benchmark_returns, cursor: int, n_bars: int):
    if benchmark_returns is None:
        return None
    start = max(cursor, 0)
    end = start + n_bars - 1
    return benchmark_returns[start:end]


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2)
