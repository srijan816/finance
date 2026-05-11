"""Tests for quant/reporting.py"""
from quant.reporting import generate_growth_report, generate_workflow_report


def sample_bars(n=80, start_price=100.0):
    from datetime import date, timedelta

    rows = []
    price = start_price
    start = date(2024, 1, 1)
    for i in range(n):
        price *= 1.001
        rows.append(((start + timedelta(days=i)).isoformat(), price, price, price, price, 1000))
    return rows


def test_generate_growth_report(tmp_path, monkeypatch):
    import quant.data

    monkeypatch.setattr(quant.data, "fetch_bars", lambda ticker, start, end: sample_bars(start_price=100 if ticker != "SPY" else 400))
    out = tmp_path / "growth.html"
    path = generate_growth_report(["AAPL", "MSFT"], output_path=str(out))
    text = out.read_text()
    assert path == str(out)
    assert "Growth of $10,000" in text
    assert "[${quality.level" in text
    assert "researchGradeStatus" in text
    assert "AAPL" in text


def test_generate_workflow_report(tmp_path):
    out = tmp_path / "workflow.html"
    path = generate_workflow_report(str(out))
    text = out.read_text()
    assert path == str(out)
    assert "Quant Lab Workflow" in text
    assert "Phase" in text
    assert "blocked_by_data" in text
