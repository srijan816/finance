"""Tests for advanced research controls added after the audit."""
from datetime import date, timedelta

import pandas as pd

from quant.backtest_diagnostics import deflated_sharpe_probability, probability_of_backtest_overfitting
from quant.execution_model import estimate_implementation_shortfall
from quant.factor_diagnostics import factor_diagnostics
from quant.features import add_cross_sectional_features
from quant.monitoring import monitoring_snapshot
from quant.news import lexicon_sentiment
from quant.portfolio_optimizer import optimize_recommendation_portfolio
from quant.regime import classify_market_regime
from quant.validation_purged import default_embargo_days, purge_and_embargo_train
from quant.workflow import workflow_status


def test_purge_removes_overlapping_training_labels():
    train = pd.DataFrame({
        "sample_date": ["2024-01-01", "2024-01-10", "2024-04-01"],
        "label_start_date": ["2024-01-01", "2024-01-10", "2024-04-01"],
        "label_end_date": ["2024-02-15", "2024-02-20", "2024-04-30"],
    })
    test = pd.DataFrame({
        "sample_date": ["2024-01-20"],
        "label_start_date": ["2024-01-20"],
        "label_end_date": ["2024-03-20"],
    })
    purged = purge_and_embargo_train(train, test, embargo_days=10)
    assert list(purged["sample_date"].dt.strftime("%Y-%m-%d")) == ["2024-04-01"]
    assert default_embargo_days(63) == 10


def test_cross_sectional_features_are_date_neutral():
    frame = pd.DataFrame({
        "sample_date": ["2024-01-01"] * 3 + ["2024-01-02"] * 3,
        "ticker": ["A", "B", "C", "A", "B", "C"],
        "sector": ["tech", "tech", "staples", "tech", "tech", "staples"],
        "mom": [1.0, 2.0, 3.0, 2.0, 4.0, 6.0],
    })
    out = add_cross_sectional_features(frame, ["mom"], sector_col="sector")
    assert round(float(out.groupby("sample_date")["mom_xsec_z"].mean().abs().max()), 8) == 0.0
    assert "mom_sector_z" in out


def test_factor_diagnostics_reports_ic_and_spread():
    records = []
    start = date(2024, 1, 1)
    for d in range(4):
        for i, ticker in enumerate(["A", "B", "C", "D", "E"]):
            records.append({
                "date": (start + timedelta(days=d)).isoformat(),
                "asset": ticker,
                "factor": i,
                "forward_return": i / 100,
                "group": "g1" if i < 3 else "g2",
            })
    result = factor_diagnostics(pd.DataFrame(records), group_col="group")
    assert result["mean_ic"] > 0.9
    assert result["top_bottom_spread"] > 0
    assert "ic_by_group" in result


def test_optimizer_shortfall_monitoring_and_regime():
    recommendations = [
        {"ticker": "AAPL", "predicted_63d_active_return": 0.05},
        {"ticker": "MSFT", "predicted_63d_active_return": 0.03},
    ]
    returns = {"AAPL": [0.01, 0.0, 0.02, -0.01], "MSFT": [0.005, 0.002, 0.004, -0.003]}
    portfolio = optimize_recommendation_portfolio(recommendations, returns, capital=10_000)
    assert portfolio["allocations"]
    shortfall = estimate_implementation_shortfall(side="buy", quantity=10, decision_price=100, commission_bps=1)
    assert shortfall["total_shortfall"] > 0
    monitor = monitoring_snapshot([
        {"date": "2024-01-01", "prediction": 0.1, "realized_return": 0.2},
        {"date": "2024-01-01", "prediction": 0.0, "realized_return": -0.1},
    ])
    assert monitor["mean_ic"] > 0
    regime = classify_market_regime([100 + i for i in range(90)])
    assert regime["regime"] in {"bull_trend", "low_vol_chop"}


def test_overfit_diagnostics_news_and_workflow():
    dsr = deflated_sharpe_probability(1.0, n_observations=60, n_trials=5)
    pbo = probability_of_backtest_overfitting([1.0, 2.0], [0.5, -0.1])
    assert 0 <= dsr["probability"] <= 1
    assert pbo["pbo"] == 1.0
    assert lexicon_sentiment("company beats estimates and raises guidance") > 0
    workflow = workflow_status()
    assert len(workflow["phases"]) == 12
    assert workflow["phases"][0]["status"] == "implemented"
