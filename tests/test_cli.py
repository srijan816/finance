"""Tests for quant CLI."""
import pytest
from click.testing import CliRunner
from quant.cli import app

runner = CliRunner()

def test_cli_analyze_dry_run():
    result = runner.invoke(app, ["analyze", "NVDA", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output

def test_cli_backtest():
    result = runner.invoke(app, ["backtest", "--tickers", "AAPL,MSFT", "--from-date", "2024-01-01", "--to-date", "2024-03-01"])
    assert result.exit_code == 0

def test_cli_llm_check(monkeypatch):
    from quant import decide

    monkeypatch.setattr(decide, "check_llm", lambda: {
        "ok": True,
        "provider": "MiniMax Anthropic",
        "model": "MiniMax-M2.7",
        "message": "OK",
    })
    result = runner.invoke(app, ["llm-check"])
    assert result.exit_code == 0
    assert "is working" in result.output

def test_cli_process():
    result = runner.invoke(app, ["process"])
    assert result.exit_code == 0
    assert "Decision Process" in result.output

def test_cli_validate(monkeypatch):
    from quant import validation

    monkeypatch.setattr(validation, "walk_forward_validate", lambda *args, **kwargs: {
        "ticker": "AAPL",
        "strategy": "sma_cross",
        "summary": {
            "n_valid": 2,
            "n_windows": 2,
            "median_sharpe": 1.2,
            "median_total_return": 4.5,
            "worst_drawdown": 3.2,
            "positive_windows": 100.0,
        },
    })
    result = runner.invoke(app, ["validate", "--ticker", "AAPL"])
    assert result.exit_code == 0
    assert "median Sharpe" in result.output

def test_cli_optimize(monkeypatch):
    from quant import portfolio

    monkeypatch.setattr(portfolio, "optimize_portfolio", lambda *args, **kwargs: {
        "weights": {"AAPL": 0.6, "MSFT": 0.4},
        "metrics": {"sharpe": 1.5, "max_dd": -0.05, "alpha": 0.02},
    })
    result = runner.invoke(app, ["optimize", "--tickers", "AAPL,MSFT"])
    assert result.exit_code == 0
    assert "AAPL=60.0%" in result.output

def test_cli_decision_audit(monkeypatch):
    from quant import audit

    monkeypatch.setattr(audit, "audit_historical_decisions", lambda *args, **kwargs: {
        "ticker": "AAPL",
        "strategy": "momentum",
        "summary": {
            "n_decisions": 10,
            "accuracy": 60.0,
            "brier_score": 0.22,
            "avg_forward_return": 1.1,
            "avg_active_return": 0.4,
            "avg_decision_edge": 0.6,
            "buy_accuracy": 66.7,
            "hold_accuracy": 50.0,
        },
    })
    result = runner.invoke(app, ["decision-audit", "--ticker", "AAPL"])
    assert result.exit_code == 0
    assert "decisions=10" in result.output

def test_cli_decision_audit_batch(monkeypatch):
    from quant import audit

    monkeypatch.setattr(audit, "audit_universe_decisions", lambda *args, **kwargs: {
        "summary": {"n_decisions": 20, "accuracy": 55.0, "brier_score": 0.25, "avg_decision_edge": 0.2},
        "per_ticker": {
            "AAPL": {"n_decisions": 10, "accuracy": 60.0, "buy_accuracy": 70.0, "hold_accuracy": 45.0},
            "MSFT": {"n_decisions": 10, "accuracy": 50.0, "buy_accuracy": 55.0, "hold_accuracy": 45.0},
        },
    })
    result = runner.invoke(app, ["decision-audit-batch", "--tickers", "AAPL,MSFT"])
    assert result.exit_code == 0
    assert "universe" in result.output
    assert "AAPL" in result.output

def test_cli_paper_sim(monkeypatch):
    from quant import simulator

    monkeypatch.setattr(simulator, "simulate_historical_paper", lambda *args, **kwargs: {
        "initial_capital": 10_000.0,
        "total_contributed": 10_000.0,
        "final_equity": 12_000.0,
        "profit_on_contributed_capital": 0.2,
        "benchmark": "SPY",
        "benchmark_final_equity": 11_000.0,
        "metrics": {"total_return": 0.2, "sharpe": 1.1, "max_dd": -0.08},
    })
    result = runner.invoke(app, ["paper-sim", "--tickers", "AAPL,MSFT"])
    assert result.exit_code == 0
    assert "contributed $10,000.00 -> $12,000.00" in result.output

def test_cli_paper_status():
    result = runner.invoke(app, ["paper", "status"])
    assert result.exit_code == 0
    assert isinstance(result.output, str)

def test_cli_brief(monkeypatch):
    from quant import briefing

    monkeypatch.setattr(briefing, "generate_brief", lambda tickers: "/tmp/brief.md")
    result = runner.invoke(app, ["brief", "--tickers", "AAPL,MSFT"])
    assert result.exit_code == 0
    assert "Briefing written" in result.output


def test_cli_workflow_report(monkeypatch):
    from quant import reporting

    monkeypatch.setattr(reporting, "generate_workflow_report", lambda output_path=None: "/tmp/workflow.html")
    result = runner.invoke(app, ["workflow-report"])
    assert result.exit_code == 0
    assert "Workflow report written" in result.output


def test_cli_web(monkeypatch):
    from quant import webapp

    called = {}

    def fake_run(host="127.0.0.1", port=8765, open_browser=True):
        called["host"] = host
        called["port"] = port
        called["open_browser"] = open_browser

    monkeypatch.setattr(webapp, "run_web_app", fake_run)
    result = runner.invoke(app, ["web", "--port", "9999", "--no-open"])
    assert result.exit_code == 0
    assert called == {"host": "127.0.0.1", "port": 9999, "open_browser": False}


def test_cli_allocate_budget(monkeypatch):
    from quant import allocation_planner

    monkeypatch.setattr(allocation_planner, "plan_budget_allocation", lambda **kwargs: {
        "capital": kwargs["capital"],
        "primary_engine": "v2",
        "plans": [{
            "engine": "v2",
            "allocation": {
                "deployable_capital": 18_000.0,
                "cash": 2_000.0,
                "allocations": [{"ticker": "AAPL", "allocation": 1_000.0, "shares_at_entry": 5, "entry": 200, "stop": 180, "target": 240}],
            },
        }],
        "research_grade_status": {"level": "DEMO", "summary": "test"},
    })
    result = runner.invoke(app, ["allocate-budget", "--capital", "20000"])
    assert result.exit_code == 0
    assert "primary engine: v2" in result.output


def test_cli_research_prompt():
    result = runner.invoke(app, ["research-prompt", "--as-of", "2026-05-09"])
    assert result.exit_code == 0
    assert "Use only information published on or before 2026-05-09" in result.output
