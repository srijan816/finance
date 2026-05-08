"""Daily morning briefing generator."""
from datetime import date
from pathlib import Path
from quant.decide import run_analysis

DEFAULT_WATCHLIST = ["NVDA", "AAPL", "MSFT", "GOOGL", "TSLA"]

def generate_brief(tickers=None):
    """Generate morning briefing for watchlist. Returns path to written file."""
    if tickers is None:
        tickers = DEFAULT_WATCHLIST

    out_dir = Path(__file__).parent.parent / "briefings"
    out_dir.mkdir(exist_ok=True)
    today_str = date.today().isoformat()
    out_path = out_dir / f"{today_str}.md"

    lines = [
        f"# Morning Briefing — {today_str}",
        "",
        f"**Watchlist:** {', '.join(tickers)}",
        "",
    ]

    for ticker in tickers:
        lines.append(f"## {ticker}")
        lines.append("")
        try:
            analysis = run_analysis(ticker, today_str, lightweight=True)
            lines.append(analysis)
        except Exception as e:
            lines.append(f"Analysis unavailable: {e}")
        lines.append("")

    content = "\n".join(lines)
    out_path.write_text(content)
    return str(out_path)
