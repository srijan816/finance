"""Research-grade status labels for quant outputs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping


DEMO = "DEMO"
RESEARCH = "RESEARCH"
PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"

YFINANCE_ALIASES = {"yfinance", "yahoo", "yahoo/yfinance", "yfinance/yahoo"}


def research_grade_status(
    *,
    data_source: str = "yfinance",
    universe_name: str | None = None,
    universe_metadata: Mapping[str, Any] | None = None,
    validation_method: str = "",
    has_point_in_time_universe: bool | None = None,
    has_survivorship_bias_free_universe: bool | None = None,
    has_delisted_coverage: bool = False,
    has_security_master: bool = False,
    has_purged_validation: bool = False,
    has_cpcv: bool = False,
    has_dsr_pbo: bool = False,
    has_risk_optimizer: bool = False,
    has_execution_shortfall: bool = False,
    feature_sources: list[str] | None = None,
    notes: list[str] | None = None,
) -> dict:
    """Classify whether an output is demo, research, or production-candidate quality."""
    metadata = dict(universe_metadata or {})
    data_source_normalized = data_source.strip().lower()
    vendor_grade_data = data_source_normalized not in YFINANCE_ALIASES

    if has_survivorship_bias_free_universe is None:
        has_survivorship_bias_free_universe = _truthy(metadata.get("survivorship_bias_free"))
    if has_point_in_time_universe is None:
        has_point_in_time_universe = bool(metadata) and metadata.get("quality") != "current_static_list"

    if _truthy(metadata.get("delisted_coverage")):
        has_delisted_coverage = True
    if _truthy(metadata.get("security_master")):
        has_security_master = True

    research_core = (
        vendor_grade_data
        and bool(has_point_in_time_universe)
        and bool(has_survivorship_bias_free_universe)
        and bool(has_delisted_coverage)
    )
    production_core = (
        research_core
        and bool(has_security_master)
        and has_purged_validation
        and has_cpcv
        and has_dsr_pbo
        and has_risk_optimizer
        and has_execution_shortfall
    )

    level = PRODUCTION_CANDIDATE if production_core else RESEARCH if research_core else DEMO
    limitations = _limitations(
        vendor_grade_data=vendor_grade_data,
        has_point_in_time_universe=bool(has_point_in_time_universe),
        has_survivorship_bias_free_universe=bool(has_survivorship_bias_free_universe),
        has_delisted_coverage=has_delisted_coverage,
        has_security_master=has_security_master,
        has_purged_validation=has_purged_validation,
        has_cpcv=has_cpcv,
        has_dsr_pbo=has_dsr_pbo,
        has_risk_optimizer=has_risk_optimizer,
        has_execution_shortfall=has_execution_shortfall,
    )

    return {
        "level": level,
        "summary": _summary(level, limitations),
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "data_source": data_source,
        "vendor_grade_data": vendor_grade_data,
        "universe_name": universe_name,
        "universe_source": metadata.get("source") or ("user_supplied_tickers" if universe_name else "unspecified"),
        "has_point_in_time_universe": bool(has_point_in_time_universe),
        "has_survivorship_bias_free_universe": bool(has_survivorship_bias_free_universe),
        "has_delisted_coverage": bool(has_delisted_coverage),
        "has_security_master": bool(has_security_master),
        "validation_method": validation_method,
        "has_purged_validation": bool(has_purged_validation),
        "has_cpcv": bool(has_cpcv),
        "has_dsr_pbo": bool(has_dsr_pbo),
        "has_risk_optimizer": bool(has_risk_optimizer),
        "has_execution_shortfall": bool(has_execution_shortfall),
        "feature_sources": feature_sources or ["price_volume"],
        "limitations": limitations,
        "required_upgrades": _required_upgrades(limitations),
        "notes": notes or [],
    }


def status_badge_line(status: Mapping[str, Any]) -> str:
    """Human-readable one-line status for CLI and reports."""
    level = status.get("level", DEMO)
    summary = status.get("summary", "")
    return f"[{level}] {summary}".strip()


def attach_research_status(result: dict, **kwargs) -> dict:
    result["research_grade_status"] = research_grade_status(**kwargs)
    return result


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "survivorship_bias_free"}
    return False


def _limitations(**flags: bool) -> list[str]:
    items = []
    if not flags["vendor_grade_data"]:
        items.append("uses_yfinance_or_yahoo_research_data")
    if not flags["has_point_in_time_universe"]:
        items.append("no_verified_point_in_time_universe")
    if not flags["has_survivorship_bias_free_universe"]:
        items.append("survivorship_bias_not_eliminated")
    if not flags["has_delisted_coverage"]:
        items.append("missing_delisted_security_coverage")
    if not flags["has_security_master"]:
        items.append("missing_security_master_or_permanent_ids")
    if not flags["has_purged_validation"]:
        items.append("no_purged_embargoed_validation")
    if not flags["has_cpcv"]:
        items.append("no_cpcv_validation_distribution")
    if not flags["has_dsr_pbo"]:
        items.append("no_dsr_or_pbo_multiple_testing_correction")
    if not flags["has_risk_optimizer"]:
        items.append("no_integrated_risk_optimizer")
    if not flags["has_execution_shortfall"]:
        items.append("no_implementation_shortfall_model")
    return items


def _required_upgrades(limitations: list[str]) -> list[str]:
    mapping = {
        "uses_yfinance_or_yahoo_research_data": "Use licensed/vendor-grade historical data for research-grade claims.",
        "no_verified_point_in_time_universe": "Use a point-in-time universe with membership effective dates.",
        "survivorship_bias_not_eliminated": "Include inactive/delisted securities and historical constituent membership.",
        "missing_delisted_security_coverage": "Model delisting dates and delisting returns.",
        "missing_security_master_or_permanent_ids": "Map symbols through a security master with permanent IDs.",
        "no_purged_embargoed_validation": "Validate overlapping labels with purge and embargo.",
        "no_cpcv_validation_distribution": "Run CPCV or comparable path-distribution validation.",
        "no_dsr_or_pbo_multiple_testing_correction": "Track tried variants and apply DSR/PBO-style corrections.",
        "no_integrated_risk_optimizer": "Convert alpha to weights with covariance, exposure, and turnover constraints.",
        "no_implementation_shortfall_model": "Model spread, slippage, commission, fill probability, and missed fills.",
    }
    return [mapping[item] for item in limitations if item in mapping]


def _summary(level: str, limitations: list[str]) -> str:
    if level == PRODUCTION_CANDIDATE:
        return "Production-candidate output with point-in-time data, robust validation, risk sizing, and execution shortfall controls."
    if level == RESEARCH:
        return "Research-grade data foundation, but production promotion still depends on validation, risk, and execution controls."
    if "survivorship_bias_not_eliminated" in limitations:
        return "Demo-grade output; survivorship bias is not eliminated, so performance is directional only."
    return "Demo-grade output; useful for exploration, not production evidence."
