"""Budget-to-target allocation planner for the web UI."""
from __future__ import annotations

import os
from typing import Sequence

import numpy as np

from quant.allocation import allocate_from_recommendations
from quant.research_status import research_grade_status


DEFAULT_ALLOC_TICKERS = [
    "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "AMD",
    "TXN", "AMAT", "CAT", "CSCO", "XLK",
]


def plan_budget_allocation(
    capital: float,
    tickers: Sequence[str] | None = None,
    engine: str = "v2",
    start: str = "2018-01-01",
    end: str = "2026-05-09",
    benchmark: str = "SPY",
    top_n: int = 12,
    strategy: str = "momentum",
) -> dict:
    """Create a simple target-allocation plan for a user-entered budget."""
    tickers = [ticker.upper() for ticker in (tickers or DEFAULT_ALLOC_TICKERS)]
    engine = engine.lower()
    if capital <= 0:
        raise ValueError("capital must be positive")
    if engine not in {"v1", "v2", "both"}:
        raise ValueError("engine must be v1, v2, or both")

    plans = []
    if engine in {"v2", "both"}:
        plans.append(_v2_plan(capital, tickers, start, end, benchmark, top_n))
    if engine in {"v1", "both"}:
        plans.append(_v1_plan(capital, tickers, start, end, strategy))

    primary = next((plan for plan in plans if plan["engine"] == "v2" and "error" not in plan), plans[0])
    tickers_in_plan = [
        row["ticker"]
        for row in primary.get("allocation", {}).get("allocations", [])
        if "ticker" in row
    ]
    return {
        "capital": round(capital, 2),
        "requested_engine": engine,
        "primary_engine": primary["engine"],
        "plans": plans,
        "ibkr_manual_setup": ibkr_manual_setup(primary),
        "manual_tracking": _manual_tracking(primary),
        "orthogonal_research": _orthogonal_research(tickers_in_plan),
        "research_grade_status": research_grade_status(
            data_source=_configured_data_source(),
            universe_name="current_or_user_supplied_ticker_list",
            validation_method="allocation_cockpit_current_signal",
            has_purged_validation=primary.get("engine") == "v2",
            has_dsr_pbo=primary.get("engine") == "v2",
            has_risk_optimizer=False,
            has_execution_shortfall=True,
            feature_sources=["price_volume"],
            notes=[
                "Allocation cockpit is for manual execution and paper tracking. It remains demo-grade until PIT/delisted data and live monitoring evidence exist.",
            ],
        ),
    }


def _v2_plan(capital: float, tickers: list[str], start: str, end: str, benchmark: str, top_n: int) -> dict:
    from quant.technical_v2 import latest_recommendations

    try:
        recommendations = latest_recommendations(tickers, start=start, end=end, benchmark=benchmark, top_n=max(top_n, 8))
        allocation = allocate_from_recommendations(recommendations["recommendations"], capital)
        expected_edge = _weighted_expected_edge(allocation["allocations"])
        return {
            "engine": "v2",
            "label": "V2 calibrated technical engine",
            "allocation": allocation,
            "model": recommendations.get("model", {}),
            "validation": recommendations.get("validation", {}),
            "expectation_path": expectation_path(capital, expected_edge, source="v2_model_edge"),
            "reasoning": _v2_reasoning(expected_edge),
        }
    except Exception as exc:
        return {"engine": "v2", "error": str(exc)}


def _v1_plan(capital: float, tickers: list[str], start: str, end: str, strategy: str) -> dict:
    from quant.data import fetch_bars
    from quant.simulator import _target_weights

    bars_by_ticker = {ticker: fetch_bars(ticker, start, end) for ticker in tickers}
    close_maps = {
        ticker: {row[0]: float(row[4]) for row in bars}
        for ticker, bars in bars_by_ticker.items()
        if bars
    }
    common_dates = sorted(set.intersection(*(set(values) for values in close_maps.values()))) if close_maps else []
    if len(common_dates) < 253:
        return {"engine": "v1", "error": "Not enough overlapping price history for V1 allocation."}
    closes = {
        ticker: np.asarray([close_maps[ticker][date] for date in common_dates], dtype=float)
        for ticker in close_maps
    }
    target_weights = _target_weights(closes, list(closes), strategy, len(common_dates) - 1, max_positions=8)
    latest_date = common_dates[-1]
    allocations = []
    for ticker, weight in sorted(target_weights.items(), key=lambda item: item[1], reverse=True):
        if weight <= 0:
            continue
        price = close_maps[ticker][latest_date]
        amount = capital * 0.90 * weight
        allocations.append({
            "ticker": ticker,
            "allocation": round(amount, 2),
            "allocation_pct": round(amount / capital, 4),
            "entry_style": "market_or_limit_manual",
            "entry": round(price, 2),
            "shares_at_entry": round(amount / price, 4) if price else 0.0,
            "why": f"V1 {strategy} signal selected this name; equal-weight baseline.",
        })
    invested = sum(row["allocation"] for row in allocations)
    allocation = {
        "capital": round(capital, 2),
        "deployable_capital": round(capital * 0.90, 2),
        "cash": round(capital - invested, 2),
        "allocations": allocations,
        "exclusions": [],
        "policy": {
            "allocation": "V1 equal-weight across current BUY signals, 10% cash reserve.",
            "strategy": strategy,
        },
    }
    return {
        "engine": "v1",
        "label": "V1 deterministic baseline",
        "allocation": allocation,
        "expectation_path": expectation_path(capital, 0.0, source="v1_no_calibrated_edge"),
        "reasoning": [
            "V1 is shown as a simple baseline, not as the preferred recommendation engine.",
            "No model edge is assumed for the expectation graph because V1 has no calibrated forward-return forecast.",
        ],
    }


def _weighted_expected_edge(allocations: Sequence[dict]) -> float:
    total = sum(float(row.get("allocation", 0.0)) for row in allocations)
    if total <= 0:
        return 0.0
    return sum(
        float(row.get("allocation", 0.0)) / total * float(row.get("predicted_63d_active_return") or 0.0)
        for row in allocations
    )


def expectation_path(capital: float, expected_63d_edge: float, source: str = "v2_model_edge") -> dict:
    """Return scenario values from current model edge. Not a promise."""
    horizons = [
        ("5d", 5),
        ("21d", 21),
        ("63d", 63),
        ("6m", 126),
        ("1y", 252),
        ("3y", 756),
    ]
    scenarios = {
        "adverse": -abs(expected_63d_edge),
        "conservative": expected_63d_edge * 0.35,
        "base": expected_63d_edge * 0.65,
        "upside": expected_63d_edge,
    }
    series = []
    for label, multiplier in scenarios.items():
        values = []
        for horizon_label, days in horizons:
            periods = days / 63
            value = capital * ((1 + multiplier) ** periods)
            values.append({"horizon": horizon_label, "days": days, "value": round(value, 2), "return_pct": round((value / capital - 1) * 100, 2)})
        series.append({"scenario": label, "values": values})
    return {
        "expected_63d_active_edge": round(expected_63d_edge, 6),
        "basis": _expectation_basis(source),
        "series": series,
    }


def _expectation_basis(source: str) -> str:
    if source == "v1_no_calibrated_edge":
        return "V1 has no calibrated forward-return estimate, so this path intentionally assumes no model edge. It is a neutral scenario scaffold, not a forecast."
    return "Current weighted V2 predicted 63-trading-day active return. Longer horizons mechanically compound the same edge and should be treated as scenario math, not a forecast."


def ibkr_manual_setup(plan: dict) -> dict:
    allocation = plan.get("allocation", {})
    orders = []
    for row in allocation.get("allocations", []):
        orders.append({
            "ticker": row["ticker"],
            "action": "BUY",
            "target_notional": row.get("allocation"),
            "estimated_quantity": row.get("shares_at_entry"),
            "suggested_order_type": "Limit",
            "limit_reference": row.get("entry"),
            "stop_reference": row.get("stop"),
            "note": "Enter manually in IBKR. Prefer staged limit orders; do not chase above the app's reference price.",
        })
    return {
        "mode": "manual_copy_only",
        "steps": [
            "Open IBKR manually and confirm available cash.",
            "For each row, create a BUY limit order near the reference entry.",
            "Use the estimated quantity as a starting point; round according to whether your account supports fractional shares.",
            "If using stops, enter them only after the position fills and verify the stop is below entry.",
            "Record the real fill back into Quant Lab's trade journal/paper tracker when available.",
        ],
        "orders": orders,
        "cash_reserve": allocation.get("cash"),
    }


def _v2_reasoning(expected_edge: float) -> list[str]:
    return [
        "V2 is preferred because it has calibrated forward active-return estimates and purged validation diagnostics.",
        "Allocation still uses demo-grade yfinance/current-universe data unless a PIT/delisted data source is installed.",
        f"The weighted model-implied 63-day active edge for invested capital is {expected_edge * 100:.2f}%. Treat this as a scenario input, not a guarantee.",
    ]


def _manual_tracking(primary: dict) -> dict:
    try:
        from quant.trade_journal import compare_to_plan

        return compare_to_plan(primary)
    except Exception as exc:
        return {
            "mode": "manual_shadow_tracking",
            "error": str(exc),
            "description": "Trade journal comparison was unavailable for this run.",
        }


def _orthogonal_research(tickers: list[str]) -> dict:
    try:
        from quant.orthogonal import research_summary_for_tickers

        return {
            "status": "manual_notes_visible_not_model_promoted",
            "summary_by_ticker": research_summary_for_tickers(tickers),
            "workflow": [
                "Add timestamped research notes with published_at/available_at.",
                "Use them as human-readable decision context first.",
                "Promote to model features only after PIT validation and leakage controls are in place.",
            ],
        }
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}


def _configured_data_source() -> str:
    if os.getenv("QUANT_DATA_SOURCE", "").strip().lower() == "norgate":
        return "norgate_ascii_import"
    return "yfinance"
