"""Alpaca paper trading client."""
import os, requests
from typing import Optional

PAPER_BASE = "https://paper-api.alpaca.markets"
ALPACA_KEY = os.environ.get("ALPACA_KEY", "")
ALPACA_SECRET = os.environ.get("ALPACA_SECRET", "")

HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}

def has_keys() -> bool:
    return bool(ALPACA_KEY and ALPACA_SECRET)

def account_status() -> str:
    if not has_keys():
        return "⚠️  Alpaca keys not configured (ALPACA_KEY/ALPACA_SECRET in .env). Paper trading disabled."
    try:
        resp = requests.get(f"{PAPER_BASE}/v2/account", headers=HEADERS, timeout=10)
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
        resp = requests.post(f"{PAPER_BASE}/v2/orders", json=payload, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return f"⚠️  Order failed: {resp.status_code} {resp.text[:100]}"
        order = resp.json()
        filled = order.get("filled_avg_price") or "MARKET"
        return f"✅ {order['side'].upper()} {order['qty']} {order['symbol']} @ ${filled}"
    except Exception as e:
        return f"⚠️  Connection error: {e}"
