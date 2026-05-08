"""CLI for quant lab — Click-based."""
import os, click, sys
from pathlib import Path

@click.group()
def app():
    """Quant Lab — Personal Quant Research Lab."""
    pass

@app.command()
@click.argument("ticker")
@click.option("--date", default="2025-01-15", help="Trade date")
@click.option("--dry-run", is_flag=True, help="Dry run only")
def analyze(ticker: str, date: str, dry_run: bool):
    """Run multi-agent analysis on a ticker."""
    from quant.decide import run_analysis
    if dry_run:
        click.echo(f"[DRY RUN] Would analyze {ticker} on {date}")
        return
    result = run_analysis(ticker.upper(), date)
    click.echo(result)

@app.command()
@click.option("--tickers", required=True, help="Comma-separated tickers")
@click.option("--from-date", "--from", "start", default="2023-01-01")
@click.option("--to-date", "--to", "end", default="2025-01-01")
@click.option("--strategy", default="agent")
def backtest(tickers: str, start: str, end: str, strategy: str):
    """Run backtest over tickers."""
    from quant.backtest import run_backtest
    ticker_list = [t.strip() for t in tickers.split(",")]
    results = run_backtest(ticker_list, start, end, strategy)
    for r in results:
        if "error" in r:
            click.echo(f"  ⚠️  {r['ticker']}: {r['error']}")
        else:
            click.echo(f"  {r['ticker']}: Sharpe={r['sharpe']}, MaxDD={r['max_dd']}%, WinRate={r['win_rate']}%")

@click.group()
def paper():
    """Paper trading commands."""
    pass

app.add_command(paper)

@paper.command(name="status")
def paper_status():
    """Check Alpaca paper status."""
    from quant.paper import account_status
    click.echo(account_status())

@paper.command(name="buy")
@click.argument("ticker")
@click.option("--qty", default=10, type=int)
def paper_buy(ticker: str, qty: int):
    """Execute a paper BUY order."""
    from quant.paper import execute_paper
    result = execute_paper("buy", ticker.upper(), qty)
    click.echo(result)

@paper.command(name="sell")
@click.argument("ticker")
@click.option("--qty", default=10, type=int)
def paper_sell(ticker: str, qty: int):
    """Execute a paper SELL order."""
    from quant.paper import execute_paper
    result = execute_paper("sell", ticker.upper(), qty)
    click.echo(result)

@app.command()
@click.option("--tickers", default="NVDA,AAPL,MSFT,GOOGL,TSLA", help="Comma-separated watchlist")
def brief(tickers: str):
    """Generate morning briefing for watchlist."""
    from quant.briefing import generate_brief
    ticker_list = [t.strip() for t in tickers.split(",")]
    path = generate_brief(ticker_list)
    click.echo(f"✅ Briefing written to {path}")

@app.command()
@click.option("--ticker", required=True)
@click.option("--days", default=30, type=int)
def improve(ticker: str, days: int):
    """Run self-improvement loop on recent decisions."""
    from quant.critic import run_critique
    result = run_critique(ticker.upper(), days)
    click.echo(result)

if __name__ == "__main__":
    app()
