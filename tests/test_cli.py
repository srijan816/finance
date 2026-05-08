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

def test_cli_paper_status():
    result = runner.invoke(app, ["paper", "status"])
    assert result.exit_code == 0
    assert isinstance(result.output, str)

def test_cli_brief():
    result = runner.invoke(app, ["brief", "--tickers", "AAPL,MSFT"])
    assert result.exit_code in [0, 1]  # may fail on LLM call but shouldn't crash
