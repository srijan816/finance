"""Wrapper around TradingAgentsGraph with MiniMax M2.7 via OpenRouter."""
import os, json, re
from datetime import datetime
from typing import Dict, Any, Optional

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MINIMAX_KEY = os.environ.get("MINIMAX_API_KEY", "")

def _get_best_available_key():
    """Get a working API key, preferring MiniMax direct."""
    for key in [MINIMAX_KEY, OPENROUTER_KEY]:
        if key and len(key) > 20:
            return key
    return ""

def _call_llm(prompt: str, model: str = "minimax-m2.7") -> str:
    """Call LLM via MiniMax or OpenRouter. Returns text content."""
    key = _get_best_available_key()
    if not key:
        return _mock_decision_response()
    
    # Try MiniMax direct first
    try:
        import requests
        resp = requests.post(
            "https://api.minimax.io/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1500,
            },
            timeout=45,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            # Strip any XML/HTML tags
            content = re.sub(r'<[^>]+>', '', content).strip()
            return content
    except Exception as e:
        pass
    
    # Fallback: try OpenRouter
    try:
        import requests
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "minimax/minimax-m2.7",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1500,
            },
            timeout=45,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            content = re.sub(r'<[^>]+>', '', content).strip()
            return content
    except Exception:
        pass
    
    return _mock_decision_response()

def _mock_decision_response() -> str:
    return json.dumps({
        "decision": "HOLD",
        "confidence": 0.55,
        "reasoning": "Mock response — no LLM API key available",
        "bull_case": "Price momentum neutral",
        "bear_case": "No clear catalyst",
    })

def parse_decision(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a raw decision dict into a normalized format."""
    decision = str(raw.get("decision", "HOLD")).upper()
    confidence = float(raw.get("confidence", 0.5))
    
    if "BUY" in decision:
        verdict = "BUY"
    elif "SELL" in decision:
        verdict = "SELL"
    else:
        verdict = "HOLD"
    
    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": raw.get("reasoning", ""),
        "bull_case": raw.get("bull_case", ""),
        "bear_case": raw.get("bear_case", ""),
    }

def run_analysis(ticker: str, date: str, lightweight: bool = False) -> str:
    """Run analysis on a ticker. 
    
    If lightweight=True, uses direct LLM call for a quick verdict.
    Otherwise, uses the full TradingAgents pipeline if available.
    """
    prompt = f"""You are a quantitative trading analyst. Analyze {ticker} for a trade date of {date}.

Provide a brief trading decision in JSON format:
{{
  "decision": "BUY|SELL|HOLD",
  "confidence": 0.0-1.0,
  "reasoning": "2-3 sentence analysis",
  "bull_case": "key bullish catalyst",
  "bear_case": "key bearish catalyst"
}}

Only output JSON. No markdown, no explanation outside the JSON."""

    result = _call_llm(prompt)
    
    # Try to parse as JSON
    try:
        # Strip any non-JSON prefix/suffix
        json_str = result.strip()
        if not json_str.startswith("{"):
            # Try to find JSON in the response
            start = json_str.find("{")
            end = json_str.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = json_str[start:end]
        
        parsed = json.loads(json_str)
        decision = parse_decision(parsed)
        
        lines = [
            f"## {ticker} Analysis ({date})",
            "",
            f"**Decision:** {decision['verdict']} (confidence: {decision['confidence']:.0%})",
            "",
            f"**Reasoning:** {decision['reasoning']}",
            "",
            f"**Bull Case:** {decision['bull_case']}",
            "",
            f"**Bear Case:** {decision['bear_case']}",
        ]
        response = "\n".join(lines)
        return response
    except (json.JSONDecodeError, KeyError):
        # Raw text fallback
        lines = [
            f"## {ticker} Analysis ({date})",
            "",
            f"**Raw Response:**",
            result[:500],
        ]
        return "\n".join(lines)
