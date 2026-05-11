"""Portfolio allocation from recommendation outputs."""
from __future__ import annotations

from typing import Sequence


SECTOR_MAP = {
    "SPY": "broad_etf",
    "QQQ": "broad_etf",
    "IWM": "broad_etf",
    "VOO": "broad_etf",
    "VTI": "broad_etf",
    "XLK": "sector_etf",
    "XLF": "sector_etf",
    "XLE": "sector_etf",
    "XLV": "sector_etf",
    "XLI": "sector_etf",
    "SMH": "semiconductor",
    "SOXX": "semiconductor",
    "NVDA": "semiconductor",
    "AVGO": "semiconductor",
    "AMD": "semiconductor",
    "INTC": "semiconductor",
    "QCOM": "semiconductor",
    "TXN": "semiconductor",
    "AMAT": "semiconductor",
    "MU": "semiconductor",
    "AAPL": "mega_tech",
    "MSFT": "mega_tech",
    "GOOGL": "mega_tech",
    "META": "mega_tech",
    "AMZN": "mega_tech",
    "NFLX": "mega_tech",
    "ORCL": "software",
    "CRM": "software",
    "ADBE": "software",
    "CSCO": "networking",
    "NOW": "software",
    "PANW": "software",
    "PLTR": "software",
    "JPM": "financial",
    "BAC": "financial",
    "GS": "financial",
    "MS": "financial",
    "V": "payments",
    "MA": "payments",
    "XOM": "energy",
    "CVX": "energy",
    "LLY": "healthcare",
    "UNH": "healthcare",
    "JNJ": "healthcare",
    "MRK": "healthcare",
    "ABBV": "healthcare",
    "WMT": "consumer",
    "COST": "consumer",
    "HD": "consumer",
    "PG": "consumer",
    "KO": "consumer",
    "PEP": "consumer",
    "MCD": "consumer",
    "DIS": "consumer",
    "CAT": "industrial",
    "GE": "industrial",
    "BA": "industrial",
    "NKE": "consumer",
    "SHOP": "growth",
    "UBER": "growth",
    "COIN": "crypto_beta",
}

SECTOR_CAPS = {
    "broad_etf": 0.35,
    "sector_etf": 0.25,
    "semiconductor": 0.30,
    "mega_tech": 0.25,
    "software": 0.20,
    "networking": 0.15,
    "financial": 0.20,
    "payments": 0.15,
    "energy": 0.15,
    "healthcare": 0.20,
    "consumer": 0.25,
    "industrial": 0.20,
    "growth": 0.15,
    "crypto_beta": 0.05,
    "unknown": 0.10,
}


def allocate_from_recommendations(
    recommendations: Sequence[dict],
    capital: float,
    max_positions: int = 8,
    cash_reserve_pct: float = 0.10,
    max_position_pct: float = 0.18,
    min_allocation: float = 500.0,
) -> dict:
    """Allocate capital to recommendation rows using explicit risk gates."""
    if capital <= 0:
        raise ValueError("capital must be positive")
    deployable = capital * (1 - cash_reserve_pct)
    max_position = capital * max_position_pct
    picks = []
    exclusions = []
    sector_used: dict[str, float] = {}

    for item in sorted(recommendations, key=lambda row: row.get("rank_score", 0), reverse=True):
        ticker = item["ticker"]
        gates = item.get("gates", {})
        sector = SECTOR_MAP.get(ticker, "unknown")
        risk_flags = []
        if not gates.get("daily_trend", False):
            risk_flags.append("daily trend gate failed")
        if not gates.get("weekly_trend", False):
            risk_flags.append("weekly trend gate failed")
        if gates.get("overbought_rsi", False) and gates.get("bearish_rsi_divergence", False):
            risk_flags.append("overbought with bearish RSI divergence")
        if item.get("rank_score", 0) <= 0:
            risk_flags.append("non-positive rank score")
        if risk_flags:
            exclusions.append({"ticker": ticker, "reasons": risk_flags})
            continue
        if len(picks) >= max_positions:
            exclusions.append({"ticker": ticker, "reasons": ["max position count reached"]})
            continue

        sector_cap = capital * SECTOR_CAPS.get(sector, SECTOR_CAPS["unknown"])
        remaining_sector = max(sector_cap - sector_used.get(sector, 0.0), 0.0)
        if remaining_sector < min_allocation:
            exclusions.append({"ticker": ticker, "reasons": [f"sector cap reached: {sector}"]})
            continue

        raw_weight = max(float(item.get("rank_score", 0)), 0.0)
        picks.append({
            "ticker": ticker,
            "sector": sector,
            "raw_weight": raw_weight,
            "max_allocation": min(max_position, remaining_sector),
            "recommendation": item,
        })
        sector_used[sector] = sector_used.get(sector, 0.0) + min(max_position, remaining_sector)

    if not picks:
        return {
            "capital": round(capital, 2),
            "deployable_capital": 0.0,
            "cash": round(capital, 2),
            "allocations": [],
            "exclusions": exclusions,
            "policy": allocation_policy(capital, max_positions, cash_reserve_pct, max_position_pct, min_allocation),
        }

    total_raw = sum(pick["raw_weight"] for pick in picks) or len(picks)
    allocations = []
    remaining = deployable
    for pick in picks:
        desired = deployable * (pick["raw_weight"] / total_raw)
        amount = min(desired, pick["max_allocation"], remaining)
        if amount >= min_allocation:
            recommendation = pick["recommendation"]
            entry_plan = _preferred_entry_plan(recommendation)
            shares = amount / entry_plan["entry"] if entry_plan["entry"] > 0 else 0.0
            allocations.append({
                "ticker": pick["ticker"],
                "sector": pick["sector"],
                "allocation": round(amount, 2),
                "allocation_pct": round(amount / capital, 4),
                "entry_style": entry_plan["style"],
                "entry": entry_plan["entry"],
                "stop": entry_plan["stop"],
                "target": entry_plan["target"],
                "shares_at_entry": round(shares, 4),
                "estimated_dollar_risk": round(max(entry_plan["entry"] - entry_plan["stop"], 0) * shares, 2),
                "rank_score": recommendation.get("rank_score"),
                "predicted_63d_active_return": recommendation.get("predicted_63d_active_return"),
                "why": _allocation_reason(recommendation),
            })
            remaining -= amount

    invested = sum(row["allocation"] for row in allocations)
    return {
        "capital": round(capital, 2),
        "deployable_capital": round(deployable, 2),
        "cash": round(capital - invested, 2),
        "allocations": allocations,
        "exclusions": exclusions,
        "policy": allocation_policy(capital, max_positions, cash_reserve_pct, max_position_pct, min_allocation),
    }


def allocation_policy(
    capital: float,
    max_positions: int,
    cash_reserve_pct: float,
    max_position_pct: float,
    min_allocation: float,
) -> dict:
    return {
        "capital": capital,
        "max_positions": max_positions,
        "cash_reserve_pct": cash_reserve_pct,
        "max_position_pct": max_position_pct,
        "min_allocation": min_allocation,
        "sector_caps": SECTOR_CAPS,
        "exclusion_rules": [
            "exclude failed daily trend gate",
            "exclude failed weekly trend gate",
            "exclude overbought RSI plus bearish RSI divergence",
            "exclude non-positive rank score",
        ],
    }


def _preferred_entry_plan(recommendation: dict) -> dict:
    gates = recommendation.get("gates", {})
    pullback = recommendation["pullback_plan"]
    breakout = recommendation["breakout_plan"]
    if gates.get("overbought_rsi", False) or recommendation["price"] > pullback["entry"] * 1.04:
        return {"style": "pullback", **pullback}
    return {"style": "breakout", **breakout}


def _allocation_reason(recommendation: dict) -> str:
    gates = recommendation.get("gates", {})
    parts = [
        f"predicted active return {recommendation.get('predicted_63d_active_return', 0) * 100:.2f}%",
        f"rank score {recommendation.get('rank_score', 0) * 100:.2f}%",
    ]
    if gates.get("weekly_trend"):
        parts.append("weekly trend confirmed")
    if gates.get("trend_strength"):
        parts.append(f"ADX trend strength {gates['trend_strength']}")
    if gates.get("volume_confirmed_breakout"):
        parts.append("breakout volume confirmed")
    return "; ".join(parts)
