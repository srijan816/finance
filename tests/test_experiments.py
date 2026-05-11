"""Tests for quant/experiments.py"""
import json

from quant import experiments


def test_save_run_writes_json(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "RUNS_DIR", tmp_path)
    path = experiments.save_run("unit", {"x": 1}, {"ok": True, "research_grade_status": {"level": "DEMO"}})
    data = json.loads((tmp_path / path.split("/")[-1]).read_text())
    assert data["kind"] == "unit"
    assert data["params"]["x"] == 1
    assert data["result"]["ok"] is True
    assert data["manifest"]["params_hash"]
    assert data["manifest"]["data_quality_level"] == "DEMO"
    assert "git_dirty" in data
