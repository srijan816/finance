"""Self-improvement loop — critic.py"""
import os, json, sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DECISIONS_DB = str(DATA_DIR / "decisions.db")

def init_db():
    conn = sqlite3.connect(DECISIONS_DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            date TEXT,
            decision TEXT,
            confidence REAL,
            reasoning TEXT,
            prompt_version TEXT,
            raw_return REAL,
            alpha_return REAL,
            reflection TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def store_decision(ticker: str, date: str, decision: str, confidence: float,
                   reasoning: str, prompt_version: str = "v1"):
    init_db()
    conn = sqlite3.connect(DECISIONS_DB)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO decisions (ticker, date, decision, confidence, reasoning, prompt_version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ticker, date, decision, confidence, reasoning, prompt_version, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_recent_decisions(ticker: str, days: int = 30) -> List[Dict]:
    init_db()
    conn = sqlite3.connect(DECISIONS_DB)
    cur = conn.cursor()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cur.execute("""
        SELECT ticker, date, decision, confidence, reasoning, prompt_version,
               raw_return, alpha_return, reflection
        FROM decisions WHERE ticker=? AND created_at > ?
        ORDER BY created_at DESC
    """, (ticker, cutoff))
    rows = cur.fetchall()
    conn.close()
    return [
        {"ticker": r[0], "date": r[1], "decision": r[2], "confidence": r[3],
         "reasoning": r[4], "prompt_version": r[5], "raw_return": r[6],
         "alpha_return": r[7], "reflection": r[8]}
        for r in rows
    ]

def run_critique(ticker: str, days: int = 30) -> str:
    """Run self-improvement critique on recent decisions."""
    decisions = get_recent_decisions(ticker, days)
    if not decisions:
        return f"No recent decisions found for {ticker} in the last {days} days. Run `quant analyze {ticker}` first."
    
    # Fetch realized returns for each decision
    from quant.data import fetch_bars
    
    critiques = []
    for dec in decisions:
        try:
            bars = fetch_bars(dec["ticker"], dec["date"], 
                            (datetime.fromisoformat(dec["date"]) + timedelta(days=7)).strftime("%Y-%m-%d"))
            if bars and len(bars) >= 2:
                entry = bars[0][4]  # first close
                exit_p = bars[-1][4]  # last close
                raw_ret = (exit_p - entry) / entry
                
                # Update with realized return
                _update_return(dec["ticker"], dec["date"], raw_ret)
                
                # Generate critique via LLM
                critique = _generate_critique(dec, raw_ret)
                critiques.append(critique)
        except Exception as e:
            critiques.append(f"Could not process {dec['date']}: {e}")
    
    if not critiques:
        return f"No critiquable decisions with data for {ticker}"
    
    return "\n---\n".join(critiques)

def _update_return(ticker: str, date: str, raw_return: float):
    conn = sqlite3.connect(DECISIONS_DB)
    cur = conn.cursor()
    cur.execute("""
        UPDATE decisions SET raw_return=? WHERE ticker=? AND date=?
    """, (raw_return, ticker, date))
    conn.commit()
    conn.close()

def _generate_critique(decision: Dict, realized_return: float) -> str:
    prompt = f"""Critique this trading decision for {decision['ticker']} on {decision['date']}:

Decision: {decision['decision']} (confidence: {decision['confidence']:.0%})
Reasoning: {decision['reasoning']}
Prompt version: {decision['prompt_version']}
Realized return: {realized_return:.1%}

Generate a brief critique covering:
1. Was the decision direction correct?
2. Was the confidence calibrated?
3. A specific, concrete improvement to the reasoning/prompt (be specific, not generic)

Keep it to 150 words max. Output as markdown."""

    # Try to use LLM
    try:
        from quant.decide import _call_llm
        result = _call_llm(prompt)
        return f"### {decision['ticker']} ({decision['date']}) — Actual: {realized_return:+.1%}\n\n{result}"
    except Exception:
        return (f"### {decision['ticker']} ({decision['date']}) — "
                f"Actual: {realized_return:+.1%}\n\n"
                f"Decision: {decision['decision']} @ {decision['confidence']:.0%}\n"
                f"Reasoning: {decision['reasoning'][:100]}...")
