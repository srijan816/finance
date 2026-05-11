"""Wrapper around TradingAgentsGraph with MiniMax M2.7."""
import os, json, re
from typing import Dict, Any
from pathlib import Path

DEFAULT_MINIMAX_BASE_URL = "https://api.minimax.io"
DEFAULT_MINIMAX_MODEL = "MiniMax-M2.7"

class LLMUnavailable(RuntimeError):
    """Raised when a configured LLM provider rejects or fails a request."""


def _load_dotenv() -> None:
    """Load simple KEY=VALUE pairs from the project .env without overriding env."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def _get_env(name: str) -> str:
    _load_dotenv()
    return os.environ.get(name, "").strip()


def _minimax_url(protocol: str, path: str) -> str:
    base = _get_env("MINIMAX_BASE_URL") or _get_env("MINIMAX_API_BASE_URL") or DEFAULT_MINIMAX_BASE_URL
    base = base.rstrip("/")

    # Accept user-provided bases like https://api.minimax.io/v1 or
    # https://api.minimax.io/anthropic and normalize them by protocol.
    if base.endswith("/v1"):
        base = base[:-3]
    if base.endswith("/anthropic"):
        base = base[: -len("/anthropic")]

    if protocol == "anthropic":
        return f"{base}/anthropic/v1/{path.lstrip('/')}"
    return f"{base}/v1/{path.lstrip('/')}"


def _normalize_minimax_model(model: str) -> str:
    aliases = {
        "minimax-m2.7": "MiniMax-M2.7",
        "minimax/m2.7": "MiniMax-M2.7",
        "minimax/minimax-m2.7": "MiniMax-M2.7",
        "codex-minimax-m2.7": "codex-MiniMax-M2.7",
    }
    return aliases.get(model.lower(), model)


def _strip_reasoning_markup(content: str) -> str:
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r"<[^>]+>", "", content)
    return content.strip()


def _api_error(provider: str, response) -> LLMUnavailable:
    try:
        data = response.json()
    except ValueError:
        data = {}

    message = ""
    if isinstance(data.get("error"), dict):
        message = data["error"].get("message", "")
    elif isinstance(data.get("base_resp"), dict):
        message = data["base_resp"].get("status_msg", "")

    detail = message or response.text[:200] or response.reason
    return LLMUnavailable(f"{provider} HTTP {response.status_code}: {detail}")


def _base_resp_ok(data: Dict[str, Any]) -> bool:
    base_resp = data.get("base_resp")
    if not isinstance(base_resp, dict):
        return True
    return base_resp.get("status_code") in (None, 0, "0")


def _extract_anthropic_text(data: Dict[str, Any]) -> str:
    if not _base_resp_ok(data):
        raise LLMUnavailable(data["base_resp"].get("status_msg", "MiniMax rejected the request"))

    content = data.get("content", [])
    if isinstance(content, str):
        return _strip_reasoning_markup(content)

    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    if not parts:
        raise LLMUnavailable("MiniMax response did not contain a text block")
    return _strip_reasoning_markup("".join(parts))


def _extract_openai_text(data: Dict[str, Any]) -> str:
    if not _base_resp_ok(data):
        raise LLMUnavailable(data["base_resp"].get("status_msg", "MiniMax rejected the request"))
    return _strip_reasoning_markup(data["choices"][0]["message"]["content"])


def _call_minimax_anthropic(prompt: str, model: str) -> str:
    key = _get_env("MINIMAX_API_KEY")
    if not key:
        raise LLMUnavailable("MINIMAX_API_KEY is not configured")

    import requests

    resp = requests.post(
        _minimax_url("anthropic", "messages"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": _normalize_minimax_model(model),
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        timeout=45,
    )
    if resp.status_code != 200:
        raise _api_error("MiniMax Anthropic", resp)
    return _extract_anthropic_text(resp.json())


def _call_minimax_openai(prompt: str, model: str) -> str:
    key = _get_env("MINIMAX_API_KEY")
    if not key:
        raise LLMUnavailable("MINIMAX_API_KEY is not configured")

    import requests

    resp = requests.post(
        _minimax_url("openai", "chat/completions"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": _normalize_minimax_model(model),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_completion_tokens": 1500,
        },
        timeout=45,
    )
    if resp.status_code != 200:
        raise _api_error("MiniMax OpenAI", resp)
    return _extract_openai_text(resp.json())


def _call_llm(prompt: str, model: str = DEFAULT_MINIMAX_MODEL) -> str:
    """Call MiniMax and fail closed when the configured provider is unusable."""
    if not _get_env("MINIMAX_API_KEY"):
        raise LLMUnavailable("MINIMAX_API_KEY is not configured")

    errors = []

    for caller in (_call_minimax_anthropic, _call_minimax_openai):
        try:
            return caller(prompt, model)
        except Exception as exc:
            errors.append(str(exc))

    raise LLMUnavailable("; ".join(errors) or "MiniMax request failed")


def check_llm(model: str = DEFAULT_MINIMAX_MODEL) -> Dict[str, Any]:
    """Return a small, user-facing health check for the configured LLM."""
    if not _get_env("MINIMAX_API_KEY"):
        return {
            "ok": False,
            "provider": "MiniMax",
            "model": _normalize_minimax_model(model),
            "message": "MINIMAX_API_KEY is not configured",
        }

    checks = [
        ("MiniMax Anthropic", _call_minimax_anthropic),
        ("MiniMax OpenAI", _call_minimax_openai),
    ]
    errors = []
    prompt = "Reply with exactly OK."
    for provider, caller in checks:
        try:
            text = caller(prompt, model)
            return {
                "ok": True,
                "provider": provider,
                "model": _normalize_minimax_model(model),
                "message": text[:200],
            }
        except Exception as exc:
            errors.append(f"{provider}: {exc}")

    return {
        "ok": False,
        "provider": "MiniMax",
        "model": _normalize_minimax_model(model),
        "message": "; ".join(errors),
    }


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

    try:
        result = _call_llm(prompt)
    except LLMUnavailable as exc:
        return "\n".join([
            f"## {ticker} Analysis ({date})",
            "",
            "**Analysis unavailable:** MiniMax could not produce a real response.",
            "",
            f"**Reason:** {exc}",
            "",
            "**Decision:** No trading decision generated.",
        ])
    
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
