"""Local manual trade journal for paper/live shadow tracking."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "trade_journal.sqlite"


def record_trade(
    *,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    trade_date: str,
    fees: float = 0.0,
    account: str = "manual_ibkr",
    source: str = "manual_copy_from_ibkr",
    strategy: str = "quant_lab_recommendation",
    linked_run_id: str = "",
    notes: str = "",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict:
    """Record a manually executed trade or paper fill."""
    ticker = ticker.strip().upper()
    side = side.strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if price <= 0:
        raise ValueError("price must be positive")

    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        cursor = conn.execute(
            """
            INSERT INTO trades (
                recorded_at, account, ticker, side, quantity, price, trade_date,
                fees, source, strategy, linked_run_id, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now(),
                account,
                ticker,
                side,
                float(quantity),
                float(price),
                trade_date,
                float(fees),
                source,
                strategy,
                linked_run_id,
                notes,
            ),
        )
        conn.commit()
        row_id = int(cursor.lastrowid)
    finally:
        conn.close()
    return {"id": row_id, "ticker": ticker, "side": side, "quantity": float(quantity), "price": float(price)}


def list_trades(limit: int = 100, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    """Return recent journal entries, newest first."""
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY trade_date DESC, id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()
    return [_dict(row) for row in rows]


def position_snapshot(db_path: Path | str = DEFAULT_DB_PATH) -> dict:
    """Aggregate manual trades into current signed positions."""
    trades = list_trades(limit=100_000, db_path=db_path)
    positions: dict[str, dict] = {}
    for trade in reversed(trades):
        ticker = trade["ticker"]
        qty = float(trade["quantity"])
        signed_qty = qty if trade["side"] == "BUY" else -qty
        notional = signed_qty * float(trade["price"])
        fees = float(trade.get("fees") or 0.0)
        row = positions.setdefault(ticker, {"ticker": ticker, "quantity": 0.0, "net_cost": 0.0, "fees": 0.0})
        row["quantity"] += signed_qty
        row["net_cost"] += notional + fees
        row["fees"] += fees
    for row in positions.values():
        qty = row["quantity"]
        row["avg_cost"] = round(row["net_cost"] / qty, 4) if abs(qty) > 1e-9 else 0.0
        row["quantity"] = round(qty, 6)
        row["net_cost"] = round(row["net_cost"], 2)
        row["fees"] = round(row["fees"], 2)
    return {"positions": sorted(positions.values(), key=lambda item: item["ticker"])}


def compare_to_plan(plan: dict, db_path: Path | str = DEFAULT_DB_PATH) -> dict:
    """Compare recorded manual positions to the current allocation target."""
    allocation = plan.get("allocation", {})
    positions = {row["ticker"]: row for row in position_snapshot(db_path)["positions"]}
    comparisons = []
    for target in allocation.get("allocations", []):
        ticker = target["ticker"]
        position = positions.get(ticker, {"quantity": 0.0, "avg_cost": 0.0})
        reference_price = float(target.get("entry") or 0.0)
        current_notional = float(position.get("quantity") or 0.0) * reference_price
        target_notional = float(target.get("allocation") or 0.0)
        comparisons.append({
            "ticker": ticker,
            "target_notional": round(target_notional, 2),
            "recorded_quantity": float(position.get("quantity") or 0.0),
            "reference_price": round(reference_price, 2),
            "recorded_reference_notional": round(current_notional, 2),
            "gap_notional": round(target_notional - current_notional, 2),
            "status": _gap_status(target_notional, current_notional),
        })
    return {
        "mode": "manual_shadow_tracking",
        "description": "Record real IBKR fills here after manual execution; Quant Lab compares recorded exposure with the target plan over time.",
        "comparisons": comparisons,
        "recorded_positions": list(positions.values()),
    }


def _gap_status(target: float, current: float) -> str:
    if target <= 0:
        return "no_target"
    ratio = current / target
    if 0.95 <= ratio <= 1.05:
        return "on_target"
    if ratio <= 0:
        return "not_recorded"
    if ratio < 0.95:
        return "under_target"
    return "over_target"


def _connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            account TEXT NOT NULL,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            trade_date TEXT NOT NULL,
            fees REAL NOT NULL DEFAULT 0,
            source TEXT NOT NULL,
            strategy TEXT NOT NULL,
            linked_run_id TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_ticker_date ON trades(ticker, trade_date)")
    conn.commit()


def _dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
