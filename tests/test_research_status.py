"""Tests for research-grade status labels."""
from quant.research_status import DEMO, PRODUCTION_CANDIDATE, RESEARCH, research_grade_status, status_badge_line


def test_yfinance_current_universe_is_demo():
    status = research_grade_status(data_source="yfinance", universe_name="current_list")
    assert status["level"] == DEMO
    assert "survivorship_bias_not_eliminated" in status["limitations"]
    assert "uses_yfinance_or_yahoo_research_data" in status["limitations"]
    assert status_badge_line(status).startswith("[DEMO]")


def test_vendor_point_in_time_universe_is_research():
    status = research_grade_status(
        data_source="norgate",
        universe_name="sp500_vendor",
        universe_metadata={
            "source": "vendor_export",
            "survivorship_bias_free": True,
            "delisted_coverage": True,
        },
    )
    assert status["level"] == RESEARCH
    assert status["has_survivorship_bias_free_universe"] is True
    assert status["has_delisted_coverage"] is True


def test_full_controls_are_production_candidate():
    status = research_grade_status(
        data_source="crsp",
        universe_name="crsp_all_us",
        universe_metadata={
            "source": "crsp_export",
            "survivorship_bias_free": True,
            "delisted_coverage": True,
            "security_master": True,
        },
        has_purged_validation=True,
        has_cpcv=True,
        has_dsr_pbo=True,
        has_risk_optimizer=True,
        has_execution_shortfall=True,
    )
    assert status["level"] == PRODUCTION_CANDIDATE
    assert status["limitations"] == []
