"""Manual orthogonal-data note capture for point-in-time research."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "orthogonal_research.sqlite"

MANUAL_RESEARCH_PROMPT = """You are preparing point-in-time orthogonal research for Quant Lab.

Rules:
- Use only information published on or before {as_of_date}.
- Do not infer future outcomes or mention later price moves.
- Prefer primary sources: company filings, earnings transcripts, exchange notices, regulator filings, and timestamped reputable news.
- Separate facts from interpretation.
- If sentiment is uncertain, say uncertain instead of forcing a bullish/bearish label.

For each ticker, return this structure:

Ticker:
As-of date:
Source title:
Source URL:
Published timestamp:
Source type: news | filing | earnings | analyst_revision | macro | flow | other
Facts known at that time:
Bullish evidence:
Bearish evidence:
Uncertainty / missing data:
Sentiment score from -1 to +1:
Confidence from 0 to 1:
Expected horizon: days | weeks | months | quarters
Why this is orthogonal to price/volume:
Suggested Quant Lab note:
"""


def manual_research_prompt(as_of_date: str) -> str:
    """Return the exact prompt the user can paste into a research workflow."""
    return MANUAL_RESEARCH_PROMPT.format(as_of_date=as_of_date)


def record_research_note(
    *,
    ticker: str,
    as_of: str,
    source_type: str,
    title: str,
    summary: str,
    sentiment_score: float = 0.0,
    confidence: float = 0.5,
    horizon: str = "weeks",
    published_at: str = "",
    source_url: str = "",
    notes: str = "",
    db_path: Path | str = DEFAULT_DB_PATH,
) -> dict:
    """Store a manual, timestamped orthogonal research note."""
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("ticker is required")
    if not -1.0 <= sentiment_score <= 1.0:
        raise ValueError("sentiment_score must be between -1 and 1")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        cursor = conn.execute(
            """
            INSERT INTO research_notes (
                recorded_at, ticker, as_of, published_at, available_at, source_type,
                source_url, title, summary, sentiment_score, confidence, horizon, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now(),
                ticker,
                as_of,
                published_at,
                published_at or as_of,
                source_type.strip().lower() or "other",
                source_url,
                title,
                summary,
                float(sentiment_score),
                float(confidence),
                horizon,
                notes,
            ),
        )
        conn.commit()
        note_id = int(cursor.lastrowid)
    finally:
        conn.close()
    return {"id": note_id, "ticker": ticker, "as_of": as_of, "sentiment_score": float(sentiment_score), "confidence": float(confidence)}


def list_research_notes(ticker: str = "", limit: int = 100, db_path: Path | str = DEFAULT_DB_PATH) -> list[dict]:
    """Return recent orthogonal research notes."""
    conn = _connect(db_path)
    try:
        _ensure_schema(conn)
        if ticker:
            rows = conn.execute(
                "SELECT * FROM research_notes WHERE ticker = ? ORDER BY as_of DESC, id DESC LIMIT ?",
                (ticker.strip().upper(), int(limit)),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM research_notes ORDER BY as_of DESC, id DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
    finally:
        conn.close()
    return [_dict(row) for row in rows]


def research_summary_for_tickers(tickers: list[str], limit_per_ticker: int = 3) -> dict:
    """Summarize manual notes that can later become model features."""
    summary = {}
    for ticker in tickers:
        notes = list_research_notes(ticker=ticker, limit=limit_per_ticker)
        if not notes:
            continue
        weighted = sum(float(n["sentiment_score"]) * float(n["confidence"]) for n in notes)
        confidence = sum(float(n["confidence"]) for n in notes) or 1.0
        summary[ticker] = {
            "note_count": len(notes),
            "confidence_weighted_sentiment": round(weighted / confidence, 4),
            "latest_notes": notes,
            "usage": "Stored as point-in-time manual research. It is visible for decisions but not yet promoted into the V2 price/volume model.",
        }
    return summary


def _connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS research_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            ticker TEXT NOT NULL,
            as_of TEXT NOT NULL,
            published_at TEXT NOT NULL DEFAULT '',
            available_at TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_url TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            sentiment_score REAL NOT NULL,
            confidence REAL NOT NULL,
            horizon TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_research_ticker_asof ON research_notes(ticker, as_of)")
    conn.commit()


def _dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
