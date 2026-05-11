"""Visible workflow state for the Quant Lab UI."""
from __future__ import annotations


def workflow_status() -> dict:
    phases = [
        _phase(0, "Honesty Layer", "implemented", "Outputs carry DEMO/RESEARCH/PRODUCTION_CANDIDATE status and saved runs include manifests."),
        _phase(1, "Data Integrity", "blocked_by_data", "Norgate ASCII/metadata import adapters exist, but research-grade status requires imported PIT/delisted/security-master data from the vendor."),
        _phase(2, "Purged Validation", "implemented", "Purged walk-forward helpers, conservative embargo, approximate DSR, and PBO diagnostics are available."),
        _phase(3, "Cross-Sectional Features", "implemented", "Per-date z-score/rank and sector-neutral transforms are available."),
        _phase(4, "Model/Gate Decoupling", "partial", "V2 now reports purged validation; legacy gate overlay remains visible and must be shadow-tracked before retirement."),
        _phase(5, "Factor Diagnostics", "implemented", "IC, quantile spread, turnover, rank autocorrelation, and group IC diagnostics are available."),
        _phase(6, "Risk-Aware Portfolio", "implemented", "A covariance-aware optimizer is available; full production status still needs PIT data and validated expected returns."),
        _phase(7, "Execution Shortfall", "implemented", "Spread, slippage, commission, impact, fill probability, and missed-fill shortfall estimates are available."),
        _phase(8, "Orthogonal Data", "partial", "Point-in-time news store and timestamp-safe lexicon sentiment exist; fundamentals/flow require external datasets."),
        _phase(9, "Regime Conditioning", "implemented", "Point-in-time trend/volatility regime classifier is available for model features and reporting."),
        _phase(10, "Live Monitoring", "implemented", "Rolling IC and calibration monitoring utilities are available once realized labels exist."),
        _phase(11, "Broker Gating", "blocked_by_validation", "IBKR rollout remains gated behind manual/paper/shadow/live stages and cannot outrun validation."),
    ]
    return {
        "title": "Quant Lab Research Workflow",
        "status": "research_controls_available_not_production_validated",
        "summary": (
            "The engineering controls for the phases are now present or explicitly gated. "
            "The system still cannot call current yfinance/current-universe outputs production-grade without vendor PIT data and out-of-sample evidence."
        ),
        "phases": phases,
        "decision_flow": [
            "Data source and universe selected",
            "Research-grade status computed",
            "Features built with available_at discipline",
            "Model trains and validates with purged/embargoed methods where enabled",
            "Factor diagnostics check stock-selection skill",
            "Risk optimizer converts alpha into constrained weights",
            "Execution model estimates implementation shortfall",
            "Monitoring logs predictions and waits for realized labels",
            "Broker integration remains gated until validation and monitoring pass",
        ],
    }


def _phase(number: int, name: str, status: str, detail: str) -> dict:
    return {"phase": number, "name": name, "status": status, "detail": detail}
