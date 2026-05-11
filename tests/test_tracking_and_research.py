from quant.orthogonal import list_research_notes, manual_research_prompt, record_research_note
from quant.trade_journal import compare_to_plan, list_trades, record_trade


def test_trade_journal_records_and_compares(tmp_path):
    db = tmp_path / "trades.sqlite"
    record_trade(ticker="aapl", side="buy", quantity=2, price=100, trade_date="2026-05-09", db_path=db)
    trades = list_trades(db_path=db)
    assert trades[0]["ticker"] == "AAPL"
    plan = {"allocation": {"allocations": [{"ticker": "AAPL", "allocation": 250.0, "entry": 100.0}]}}
    comparison = compare_to_plan(plan, db_path=db)
    assert comparison["comparisons"][0]["gap_notional"] == 50.0
    assert comparison["comparisons"][0]["status"] == "under_target"


def test_manual_research_prompt_and_note_store(tmp_path):
    db = tmp_path / "research.sqlite"
    prompt = manual_research_prompt("2026-05-09")
    assert "Use only information published on or before 2026-05-09" in prompt
    record_research_note(
        ticker="NVDA",
        as_of="2026-05-09",
        source_type="news",
        title="Test source",
        summary="Timestamped fact pattern.",
        sentiment_score=0.2,
        confidence=0.8,
        db_path=db,
    )
    notes = list_research_notes(ticker="NVDA", db_path=db)
    assert notes[0]["sentiment_score"] == 0.2
