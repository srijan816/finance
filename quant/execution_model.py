"""Implementation shortfall estimates for proposed orders."""
from __future__ import annotations

from typing import Sequence


def estimate_implementation_shortfall(
    *,
    side: str,
    quantity: float,
    decision_price: float,
    expected_fill_price: float | None = None,
    commission_bps: float = 0.0,
    spread_bps: float = 2.0,
    slippage_bps: float = 2.0,
    market_impact_bps: float = 0.0,
    fill_probability: float = 1.0,
    missed_alpha_bps: float = 0.0,
) -> dict:
    """Estimate explicit and implicit costs relative to decision price."""
    side = side.lower()
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    notional = abs(quantity * decision_price)
    direction = 1 if side == "buy" else -1
    effective_bps = spread_bps / 2 + slippage_bps + market_impact_bps
    modeled_fill = decision_price * (1 + direction * effective_bps / 10_000)
    fill_price = expected_fill_price if expected_fill_price is not None else modeled_fill
    explicit_fee = notional * commission_bps / 10_000
    spread_cost = notional * (spread_bps / 2) / 10_000
    slippage_cost = notional * slippage_bps / 10_000
    impact_cost = notional * market_impact_bps / 10_000
    missed_fill_cost = notional * max(0.0, 1 - fill_probability) * missed_alpha_bps / 10_000
    total = explicit_fee + spread_cost + slippage_cost + impact_cost + missed_fill_cost
    return {
        "side": side,
        "quantity": round(float(quantity), 6),
        "decision_price": round(float(decision_price), 4),
        "expected_fill_price": round(float(fill_price), 4),
        "notional": round(float(notional), 2),
        "fill_probability": round(float(fill_probability), 4),
        "components": {
            "commission": round(float(explicit_fee), 4),
            "spread": round(float(spread_cost), 4),
            "slippage": round(float(slippage_cost), 4),
            "market_impact": round(float(impact_cost), 4),
            "missed_fill_opportunity": round(float(missed_fill_cost), 4),
        },
        "total_shortfall": round(float(total), 4),
        "total_shortfall_bps": round(float(total / notional * 10_000), 4) if notional else 0.0,
    }


def shortfall_report(orders: Sequence[dict], **defaults) -> dict:
    estimates = [estimate_implementation_shortfall(**{**defaults, **order}) for order in orders]
    return {
        "orders": estimates,
        "total_shortfall": round(sum(row["total_shortfall"] for row in estimates), 4),
        "total_notional": round(sum(row["notional"] for row in estimates), 2),
    }
