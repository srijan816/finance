"""Historical paper-money portfolio simulation under prior-information rules."""
from __future__ import annotations

from typing import Dict, Sequence

import numpy as np

from quant.execution import BrokerSimulator, ExecutionConfig
from quant.metrics import summarize_performance
from quant.research_status import research_grade_status
from quant.strategies import signal_for_strategy


def simulate_historical_paper(
    tickers: Sequence[str],
    start: str,
    end: str,
    strategy: str = "momentum",
    initial_capital: float = 10_000.0,
    benchmark: str = "SPY",
    min_history: int = 252,
    rebalance_step: int = 21,
    max_positions: int = 5,
    commission_bps: float = 0.0,
    slippage_bps: float = 2.0,
    max_volume_participation: float = 0.05,
    monthly_contribution: float = 0.0,
) -> Dict:
    """Simulate paper allocation using only history available before each rebalance."""
    from quant.data import fetch_bars

    tickers = [ticker.upper() for ticker in tickers]
    bars_by_ticker = {ticker: fetch_bars(ticker, start, end) for ticker in tickers}
    if not bars_by_ticker:
        return {"error": "No tickers supplied"}

    close_maps = {
        ticker: {row[0]: float(row[4]) for row in bars}
        for ticker, bars in bars_by_ticker.items()
    }
    common_dates = sorted(set.intersection(*(set(values) for values in close_maps.values())))
    min_len = len(common_dates)
    if min_len < min_history + rebalance_step + 1:
        return {"error": f"Need at least {min_history + rebalance_step + 1} bars, got {min_len}"}

    closes = {
        ticker: np.asarray([close_maps[ticker][date] for date in common_dates], dtype=float)
        for ticker in tickers
    }
    volumes = {
        ticker: {row[0]: float(row[5]) for row in bars_by_ticker[ticker]}
        for ticker in tickers
    }

    benchmark_returns = None
    if benchmark:
        try:
            benchmark_map = {row[0]: float(row[4]) for row in fetch_bars(benchmark, start, end)}
            benchmark_closes = np.asarray([benchmark_map[date] for date in common_dates], dtype=float)
            benchmark_returns = benchmark_closes[1:] / benchmark_closes[:-1] - 1
        except (KeyError, Exception):
            benchmark_returns = None

    broker = BrokerSimulator(initial_capital, ExecutionConfig(
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_volume_participation=max_volume_participation,
    ))
    daily_returns = []
    equity_curve = [initial_capital]
    contribution_history = []
    rebalances = []
    total_turnover = 0.0
    total_contributed = initial_capital
    last_contribution_month_index = None

    benchmark_shares = 0.0
    benchmark_cash = initial_capital
    benchmark_equity_curve = [initial_capital]

    for day in range(min_history, min_len - 1):
        prices_today = {ticker: closes[ticker][day] for ticker in tickers}
        if day == min_history or (day - min_history) % rebalance_step == 0:
            contribution = 0.0
            contribution_month_index = _month_index(common_dates[day])
            if monthly_contribution > 0:
                months_due = (
                    1
                    if last_contribution_month_index is None
                    else max(0, contribution_month_index - last_contribution_month_index)
                )
                contribution = monthly_contribution * months_due
                last_contribution_month_index = contribution_month_index
            if contribution > 0:
                broker.cash += contribution
                benchmark_cash += contribution
                total_contributed += contribution
                contribution_history.append({
                    "date": common_dates[day],
                    "amount": round(contribution, 2),
                    "months_covered": int(round(contribution / monthly_contribution)) if monthly_contribution else 0,
                })

            target = _target_weights(closes, tickers, strategy, day, max_positions)
            current_weights = broker.weights(prices_today)
            turnover = sum(abs(target[ticker] - current_weights.get(ticker, 0.0)) for ticker in tickers)
            total_turnover += turnover
            execution = broker.rebalance_to_weights(
                common_dates[day],
                target,
                prices_today,
                {ticker: volumes[ticker].get(common_dates[day], 0.0) for ticker in tickers},
            )
            actual_weights = broker.weights(prices_today)
            equity_after_execution = broker.equity(prices_today)
            rebalances.append({
                "date": common_dates[day],
                "target_weights": {ticker: round(weight, 4) for ticker, weight in target.items() if weight > 0},
                "actual_weights": {ticker: round(weight, 4) for ticker, weight in actual_weights.items() if weight > 0},
                "cash": round(broker.cash / equity_after_execution, 4) if equity_after_execution > 0 else 0.0,
                "turnover": round(turnover, 4),
                "contribution": round(contribution, 2),
                "fills": execution["fills"],
                "rejected_orders": execution["rejected_orders"],
            })

            if benchmark_returns is not None and benchmark_cash > 0:
                benchmark_price = benchmark_closes[day]
                benchmark_shares += benchmark_cash / benchmark_price
                benchmark_cash = 0.0

        previous_equity = broker.equity(prices_today)
        next_prices = {ticker: closes[ticker][day + 1] for ticker in tickers}
        next_equity = broker.equity(next_prices)
        portfolio_return = next_equity / previous_equity - 1 if previous_equity > 0 else 0.0
        daily_returns.append(portfolio_return)
        equity_curve.append(next_equity)
        if benchmark_returns is not None:
            benchmark_equity_curve.append(benchmark_cash + benchmark_shares * benchmark_closes[day + 1])

    bench = None if benchmark_returns is None else benchmark_returns[min_history:min_history + len(daily_returns)]
    metrics = summarize_performance(daily_returns, bench)
    benchmark_final = None
    if benchmark_returns is not None and len(benchmark_equity_curve):
        benchmark_final = benchmark_equity_curve[-1]

    strategy_gain = float(equity_curve[-1] - total_contributed)
    benchmark_gain = None if benchmark_final is None else float(benchmark_final - total_contributed)

    return {
        "tickers": tickers,
        "strategy": strategy,
        "start": common_dates[min_history],
        "end": common_dates[min_len - 1],
        "initial_capital": round(initial_capital, 2),
        "monthly_contribution": round(monthly_contribution, 2),
        "total_contributed": round(total_contributed, 2),
        "final_equity": round(float(equity_curve[-1]), 2),
        "pnl": round(strategy_gain, 2),
        "profit_on_contributed_capital": round(strategy_gain / total_contributed, 4) if total_contributed else 0.0,
        "benchmark": benchmark if bench is not None else None,
        "benchmark_final_equity": None if benchmark_final is None else round(float(benchmark_final), 2),
        "benchmark_pnl": None if benchmark_gain is None else round(benchmark_gain, 2),
        "benchmark_profit_on_contributed_capital": (
            None if benchmark_gain is None or not total_contributed else round(benchmark_gain / total_contributed, 4)
        ),
        "metrics": {key: round(float(value), 4) for key, value in metrics.items()},
        "contributions": contribution_history,
        "n_contributions": len(contribution_history),
        "rebalances": rebalances,
        "n_rebalances": len(rebalances),
        "avg_turnover": round(total_turnover / len(rebalances), 4) if rebalances else 0.0,
        "cost_summary": broker.cost_summary(),
        "fills": [fill.to_dict() for fill in broker.fills],
        "rejected_orders": [reject.to_dict() for reject in broker.rejected_orders],
        "assumptions": {
            "veil_of_ignorance": "Each rebalance uses closes strictly before that rebalance date.",
            "rebalance_step": rebalance_step,
            "min_history": min_history,
            "max_positions": max_positions,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "max_volume_participation": max_volume_participation,
            "monthly_contribution": monthly_contribution,
            "cash_yield": 0.0,
            "allocation": "Equal target weight across BUY signals, capped by max_positions; otherwise cash.",
            "execution": "Orders generated at rebalance close using prior close history; fills include slippage, fees, cash checks, and volume participation caps.",
            "contributions": "Monthly contributions are added immediately before that month's first rebalance and may remain in cash if no names qualify.",
            "benchmark_contributions": "Benchmark receives the same initial capital and monthly contributions on the same rebalance dates, invested into the benchmark close.",
        },
        "research_grade_status": research_grade_status(
            data_source="yfinance",
            universe_name="user_supplied_tickers",
            validation_method="historical_paper_sim_prior_information",
            has_execution_shortfall=False,
            feature_sources=["price_volume"],
            notes=[
                "Rebalances use prior information, but the supplied ticker list may be survivorship-biased.",
            ],
        ),
    }


def _target_weights(
    closes: Dict[str, np.ndarray],
    tickers: Sequence[str],
    strategy: str,
    day: int,
    max_positions: int,
) -> Dict[str, float]:
    candidates = []
    for ticker in tickers:
        history = closes[ticker][:day]
        signal = signal_for_strategy(strategy, history)
        if len(signal) and signal[-1] > 0:
            candidates.append((ticker, _strength(strategy, history)))

    candidates.sort(key=lambda item: item[1], reverse=True)
    selected = [ticker for ticker, _ in candidates[:max_positions]]
    if not selected:
        return {ticker: 0.0 for ticker in tickers}

    weight = 1 / len(selected)
    return {ticker: weight if ticker in selected else 0.0 for ticker in tickers}


def _strength(strategy: str, history: np.ndarray) -> float:
    name = strategy.lower().replace("-", "_")
    if len(history) < 2:
        return 0.0
    if name in {"momentum", "trend"} and len(history) > 63:
        return float(history[-1] / history[-64] - 1)
    if name in {"agent", "sma", "sma_cross"} and len(history) >= 50:
        return float(history[-20:].mean() / history[-50:].mean() - 1)
    if name in {"buy_hold", "buyhold", "hold"}:
        return 1.0
    return 0.0


def _month_index(date_string: str) -> int:
    year, month = date_string[:7].split("-")
    return int(year) * 12 + int(month)
