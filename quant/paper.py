"""Alpaca paper trading client."""
import os, requests
from pathlib import Path
from typing import Optional

PAPER_BASE = "https://paper-api.alpaca.markets"


def _load_dotenv() -> None:
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


def _headers() -> dict:
    _load_dotenv()
    return {
        "APCA-API-KEY-ID": os.environ.get("ALPACA_KEY", "").strip(),
        "APCA-API-SECRET-KEY": os.environ.get("ALPACA_SECRET", "").strip(),
    }


def has_keys() -> bool:
    headers = _headers()
    return bool(headers["APCA-API-KEY-ID"] and headers["APCA-API-SECRET-KEY"])

def account_status() -> str:
    if not has_keys():
        return "⚠️  Alpaca keys not configured (ALPACA_KEY/ALPACA_SECRET in .env). Paper trading disabled."
    try:
        resp = requests.get(f"{PAPER_BASE}/v2/account", headers=_headers(), timeout=10)
        if resp.status_code != 200:
            return f"⚠️  Alpaca error: {resp.status_code} {resp.text[:100]}"
        acct = resp.json()
        return (
            f"💰 Account: ${acct.get('portfolio_value','?')} | "
            f"Equity: ${acct.get('equity','?')} | "
            f"Cash: ${acct.get('cash','?')} | "
            f"Buying Power: ${acct.get('buying_power','?')}"
        )
    except Exception as e:
        return f"⚠️  Connection error: {e}"

def execute_paper(action: str, ticker: str, qty: int) -> str:
    if not has_keys():
        return "⚠️  Alpaca keys not configured. Cannot execute paper trade."
    side = "buy" if action == "buy" else "sell"
    payload = {"symbol": ticker.upper(), "qty": qty, "side": side, "type": "market"}
    try:
        resp = requests.post(f"{PAPER_BASE}/v2/orders", json=payload, headers=_headers(), timeout=10)
        if resp.status_code != 200:
            return f"⚠️  Order failed: {resp.status_code} {resp.text[:100]}"
        order = resp.json()
        filled = order.get("filled_avg_price") or "MARKET"
        return f"✅ {order['side'].upper()} {order['qty']} {order['symbol']} @ ${filled}"
    except Exception as e:
        return f"⚠️  Connection error: {e}"
