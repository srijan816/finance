"""Tests for quant/decide.py"""
import pytest
from quant.decide import (
    LLMUnavailable,
    _call_llm,
    _extract_anthropic_text,
    _normalize_minimax_model,
    check_llm,
    parse_decision,
    run_analysis,
)

def test_parse_decision_buy():
    result = parse_decision({"decision": "BUY", "confidence": 0.8})
    assert result["verdict"] == "BUY"

def test_parse_decision_sell():
    result = parse_decision({"decision": "SELL", "confidence": 0.7})
    assert result["verdict"] == "SELL"

def test_run_analysis_lightweight(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    # Lightweight mode returns a string, not a full graph
    result = run_analysis("AAPL", "2024-01-15", lightweight=True)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "No trading decision generated" in result

def test_normalizes_minimax_model_aliases():
    assert _normalize_minimax_model("minimax-m2.7") == "MiniMax-M2.7"
    assert _normalize_minimax_model("minimax/minimax-m2.7") == "MiniMax-M2.7"

def test_extracts_text_from_anthropic_response():
    result = _extract_anthropic_text({
        "content": [
            {"type": "thinking", "thinking": "private reasoning"},
            {"type": "text", "text": "<think>hidden</think>{\"decision\":\"BUY\"}"},
        ],
        "base_resp": {"status_code": 0},
    })
    assert result == '{"decision":"BUY"}'

def test_openrouter_is_not_called_with_minimax_key(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-cp-test-token-plan-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-cp-test-token-plan-key")

    calls = []

    class Response:
        status_code = 401
        reason = "Unauthorized"
        text = '{"error":{"message":"bad auth"}}'

        def json(self):
            return {"error": {"message": "bad auth"}}

    def fake_post(url, **kwargs):
        calls.append(url)
        return Response()

    import requests
    monkeypatch.setattr(requests, "post", fake_post)

    with pytest.raises(LLMUnavailable) as excinfo:
        _call_llm("Return JSON")
    assert "bad auth" in str(excinfo.value)
    assert len(calls) == 2
    assert calls[0].endswith("/anthropic/v1/messages")
    assert calls[1].endswith("/v1/chat/completions")
    assert not any("openrouter.ai" in url for url in calls)

def test_check_llm_reports_missing_key(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    result = check_llm()
    assert result["ok"] is False
    assert "MINIMAX_API_KEY" in result["message"]
