"""Survivorship-aware simulations over imported Norgate data."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import date, datetime
from statistics import mean
from typing import Sequence

import numpy as np

from quant.execution import BrokerSimulator, ExecutionConfig
from quant.metrics import summarize_performance
from quant.norgate import _connect, _ensure_schema
from quant.research_status import research_grade_status


@dataclass(frozen=True)
class Security:
    ticker: str
    name: str
    first_date: str
    last_date: str
    exchange: str
    sector: str

    def active_on(self, date_text: str) -> bool:
        return self.first_date <= date_text and (not self.last_date or date_text <= self.last_date)


def simulate_norgate_survivorship(
    *,
    market: str = "US",
    start: str = "2024-05-09",
    end: str = "2026-05-09",
    initial_capital: float = 20_000.0,
    strategy: str = "momentum",
    lookback: int = 63,
    min_history: int = 126,
    rebalance_step: int = 21,
    max_positions: int = 10,
    min_price: float = 5.0,
    min_dollar_volume: float = 5_000_000.0,
    commission_bps: float = 0.0,
    slippage_bps: float = 2.0,
    max_volume_participation: float = 0.025,
    benchmark: str = "SPY",
    universe: str = "common_stock",
    exchanges: Sequence[str] | None = ("NYSE", "Nasdaq", "NYSE American"),
) -> dict:
    """Simulate a PIT Norgate universe without requiring all symbols to share dates."""
    if strategy != "momentum":
        raise ValueError("Only momentum is implemented for Norgate survivorship simulation.")
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")
    market = market.upper()

    securities = _load_securities(market, universe, exchanges=exchanges)
    if not securities:
        return {"error": f"No imported Norgate securities for market={market} universe={universe}"}

    bars = _load_bars(market, start, end, securities.keys())
    bars = {ticker: data for ticker, data in bars.items() if len(data["dates"]) >= min(min_history, lookback)}
    if benchmark.upper() not in bars:
        benchmark_bars = _load_bars(market, start, end, [benchmark.upper()]).get(benchmark.upper())
        if benchmark_bars:
            bars[benchmark.upper()] = benchmark_bars
    dates = _market_dates(market, start, end)
    if len(dates) < min_history + rebalance_step:
        return {"error": f"Need at least {min_history + rebalance_step} market dates, got {len(dates)}"}

    broker = BrokerSimulator(initial_capital, ExecutionConfig(
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_volume_participation=max_volume_participation,
        min_notional=25.0,
    ))
    daily_returns = []
    equity_points = []
    rebalances = []
    delist_liquidations = []
    prev_equity = initial_capital
    total_turnover = 0.0
    rebalance_indices = set(range(min_history, len(dates), rebalance_step))

    benchmark_points = _benchmark_curve(bars.get(benchmark.upper()), dates, initial_capital)
    benchmark_returns = []
    prev_benchmark = benchmark_points[0]["equity"] if benchmark_points else None

    for day_index, current_date in enumerate(dates):
        _liquidate_unpriced_positions(broker, bars, current_date, delist_liquidations)

        if day_index in rebalance_indices:
            candidates = _rank_candidates(
                securities,
                bars,
                current_date,
                lookback=lookback,
                min_history=min_history,
                min_price=min_price,
                min_dollar_volume=min_dollar_volume,
                exclude={benchmark.upper()},
            )
            selected = candidates[:max_positions]
            target_weights = {ticker: 1 / len(selected) for ticker, _score in selected} if selected else {}
            all_needed = set(broker.positions) | set(target_weights)
            prices = {
                ticker: _mark_price(bars[ticker], current_date)
                for ticker in all_needed
                if ticker in bars and _mark_price(bars[ticker], current_date) is not None
            }
            volumes = {
                ticker: _exact_volume(bars[ticker], current_date) or 0.0
                for ticker in prices
                if ticker in bars
            }
            current_weights = broker.weights(prices) if prices else {}
            turnover = sum(abs(target_weights.get(ticker, 0.0) - current_weights.get(ticker, 0.0)) for ticker in set(target_weights) | set(current_weights))
            total_turnover += turnover
            execution = broker.rebalance_to_weights(current_date, target_weights, prices, volumes) if prices else {"fills": [], "rejected_orders": []}
            rebalances.append({
                "date": current_date,
                "selected": [{"ticker": ticker, "momentum": round(score, 6)} for ticker, score in selected],
                "n_candidates": len(candidates),
                "turnover": round(turnover, 4),
                "cash": round(broker.cash, 2),
                "fills": execution["fills"],
                "rejected_orders": execution["rejected_orders"],
            })

        prices_today = {
            ticker: price
            for ticker in broker.positions
            for price in [_mark_price(bars.get(ticker, {"dates": [], "closes": []}), current_date)]
            if price is not None
        }
        equity = broker.equity(prices_today)
        if day_index >= min_history:
            daily_returns.append(equity / prev_equity - 1 if prev_equity else 0.0)
            if benchmark_points and day_index < len(benchmark_points):
                benchmark_equity = benchmark_points[day_index]["equity"]
                benchmark_returns.append(benchmark_equity / prev_benchmark - 1 if prev_benchmark else 0.0)
                prev_benchmark = benchmark_equity
        prev_equity = equity
        equity_points.append({"date": current_date, "equity": round(equity, 2), "cash": round(broker.cash, 2), "positions": len(broker.positions)})

    metrics = summarize_performance(daily_returns, benchmark_returns if benchmark_returns else None)
    final_equity = float(equity_points[-1]["equity"]) if equity_points else initial_capital
    benchmark_final = benchmark_points[-1]["equity"] if benchmark_points else None
    active_delisted = sum(1 for sec in securities.values() if sec.last_date and sec.last_date <= end)

    return {
        "market": market,
        "universe": universe,
        "strategy": strategy,
        "start": dates[min_history],
        "end": dates[-1],
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "pnl": round(final_equity - initial_capital, 2),
        "total_return_pct": round((final_equity / initial_capital - 1) * 100, 2),
        "benchmark": benchmark.upper() if benchmark_points else None,
        "benchmark_final_equity": None if benchmark_final is None else round(float(benchmark_final), 2),
        "benchmark_total_return_pct": None if benchmark_final is None else round((float(benchmark_final) / initial_capital - 1) * 100, 2),
        "metrics": {key: round(float(value), 6) for key, value in metrics.items()},
        "n_securities": len(securities),
        "n_loaded_price_series": len(bars),
        "n_delisted_or_ended_securities": active_delisted,
        "n_rebalances": len(rebalances),
        "avg_turnover": round(total_turnover / len(rebalances), 6) if rebalances else 0.0,
        "cost_summary": broker.cost_summary(),
        "delist_liquidations": delist_liquidations[:100],
        "n_delist_liquidations": len(delist_liquidations),
        "equity_curve": equity_points,
        "rebalances": rebalances,
        "assumptions": {
            "point_in_time_universe": "Each rebalance considers only securities active in the imported Norgate security master on that date.",
            "selection": "Positive trailing momentum, ranked by lookback return, after price/liquidity filters.",
            "signal_timing": "Momentum and liquidity use bars strictly before the rebalance date; execution uses the rebalance close.",
            "delistings": "If a held security has no later bar, the simulator liquidates at its last available close and records the event.",
            "universe_filter": universe,
            "exchanges": list(exchanges or []),
            "lookback": lookback,
            "min_history": min_history,
            "rebalance_step": rebalance_step,
            "max_positions": max_positions,
            "min_price": min_price,
            "min_dollar_volume": min_dollar_volume,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "max_volume_participation": max_volume_participation,
        },
        "research_grade_status": research_grade_status(
            data_source="norgate_ascii_import",
            universe_name=f"norgate_{market.lower()}_{universe}",
            universe_metadata={
                "source": "imported_norgate_security_master",
                "quality": "vendor_security_master_active_dates",
                "survivorship_bias_free": True,
                "delisted_coverage": True,
                "security_master": True,
            },
            validation_method="survivorship_aware_historical_simulation",
            has_execution_shortfall=False,
            feature_sources=["price_volume"],
            notes=[
                "This is a broad listed-security simulation, not historical index-constituent membership.",
                "The available export starts at 2024-05-09, so longer-horizon claims require a longer Norgate export/subscription window.",
            ],
        ),
    }


def _load_securities(market: str, universe: str, exchanges: Sequence[str] | None = None) -> dict[str, Security]:
    conn = _connect()
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT DISTINCT s.symbol, s.name, s.first_quoted_date, s.last_quoted_date, s.exchange, s.gics_sector
            FROM norgate_security_master s
            JOIN norgate_bars b ON b.ticker = s.symbol
            WHERE b.market = ?
            """,
            (market,),
        ).fetchall()
    finally:
        conn.close()
    securities = {}
    for row in rows:
        security = Security(
            ticker=row["symbol"],
            name=row["name"] or "",
            first_date=_clean_date(row["first_quoted_date"]) or "1900-01-01",
            last_date=_clean_date(row["last_quoted_date"]),
            exchange=row["exchange"] or "",
            sector=row["gics_sector"] or "",
        )
        if exchanges and security.exchange not in set(exchanges):
            continue
        if _include_security(security, universe):
            securities[security.ticker] = security
    return securities


def _load_bars(market: str, start: str, end: str, tickers: Sequence[str]) -> dict[str, dict]:
    tickers = sorted(set(tickers))
    if not tickers:
        return {}
    out: dict[str, dict] = {}
    conn = _connect()
    try:
        _ensure_schema(conn)
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start:chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            rows = conn.execute(
                f"""
                SELECT ticker, date, close, volume
                FROM norgate_bars
                WHERE market = ? AND date >= ? AND date <= ? AND ticker IN ({placeholders})
                ORDER BY ticker, date
                """,
                [market, start, end] + chunk,
            ).fetchall()
            for row in rows:
                item = out.setdefault(row["ticker"], {"dates": [], "closes": [], "volumes": []})
                item["dates"].append(row["date"])
                item["closes"].append(float(row["close"]))
                item["volumes"].append(float(row["volume"]))
    finally:
        conn.close()
    return out


def _market_dates(market: str, start: str, end: str) -> list[str]:
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT date FROM norgate_bars WHERE market = ? AND date >= ? AND date <= ? ORDER BY date",
            (market, start, end),
        ).fetchall()
    finally:
        conn.close()
    return [row["date"] for row in rows]


def _rank_candidates(
    securities: dict[str, Security],
    bars: dict[str, dict],
    current_date: str,
    *,
    lookback: int,
    min_history: int,
    min_price: float,
    min_dollar_volume: float,
    exclude: set[str],
) -> list[tuple[str, float]]:
    candidates = []
    for ticker, security in securities.items():
        if ticker in exclude or not security.active_on(current_date):
            continue
        series = bars.get(ticker)
        if not series:
            continue
        exact_idx = bisect_left(series["dates"], current_date)
        if exact_idx >= len(series["dates"]) or series["dates"][exact_idx] != current_date:
            continue
        history_end = exact_idx
        if history_end < max(lookback, min_history):
            continue
        prior_close = series["closes"][history_end - 1]
        lookback_close = series["closes"][history_end - lookback]
        if lookback_close <= 0 or prior_close < min_price:
            continue
        avg_dollar_volume = mean(
            close * volume
            for close, volume in zip(series["closes"][max(0, history_end - 20):history_end], series["volumes"][max(0, history_end - 20):history_end])
        )
        if avg_dollar_volume < min_dollar_volume:
            continue
        momentum = prior_close / lookback_close - 1
        if momentum > 0:
            candidates.append((ticker, float(momentum)))
    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates


def _benchmark_curve(series: dict | None, dates: Sequence[str], initial_capital: float) -> list[dict]:
    if not series or not dates:
        return []
    first_price = _mark_price(series, dates[0])
    if not first_price:
        return []
    shares = initial_capital / first_price
    return [
        {"date": date_text, "equity": shares * price}
        for date_text in dates
        for price in [_mark_price(series, date_text)]
        if price is not None
    ]


def _liquidate_unpriced_positions(
    broker: BrokerSimulator,
    bars: dict[str, dict],
    current_date: str,
    events: list[dict],
) -> None:
    for ticker, quantity in list(broker.positions.items()):
        series = bars.get(ticker)
        if not series or not series["dates"]:
            continue
        if current_date > series["dates"][-1]:
            liquidation_value = quantity * float(series["closes"][-1])
            broker.cash += liquidation_value
            broker.positions.pop(ticker, None)
            events.append({
                "date": current_date,
                "ticker": ticker,
                "quantity": round(quantity, 6),
                "last_bar_date": series["dates"][-1],
                "last_close": round(float(series["closes"][-1]), 4),
                "cash_added": round(liquidation_value, 2),
            })


def _mark_price(series: dict, date_text: str) -> float | None:
    dates = series.get("dates", [])
    closes = series.get("closes", [])
    idx = bisect_right(dates, date_text) - 1
    if idx < 0:
        return None
    return float(closes[idx])


def _exact_volume(series: dict, date_text: str) -> float | None:
    idx = bisect_left(series["dates"], date_text)
    if idx >= len(series["dates"]) or series["dates"][idx] != date_text:
        return None
    return float(series["volumes"][idx])


def _include_security(security: Security, universe: str) -> bool:
    if universe == "all":
        return True
    name = security.name.lower()
    excluded = [
        " etf", "fund", "cef", "warrant", "right", " preferred", " preferred",
        "unit", "option", "debt", "note", "bond", "debenture", "acquisition corp unit",
    ]
    if any(term in name for term in excluded):
        return False
    if universe == "common_stock":
        return "common" in name or " adr" in name or name.endswith(" adr")
    raise ValueError("universe must be common_stock or all")


def _clean_date(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text[:10]).date().isoformat()
    except ValueError:
        return date.max.isoformat() if text.startswith("2029") else ""
