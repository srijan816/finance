"""CLI for quant lab — Click-based."""
import json, os, click, sys
from pathlib import Path


def _echo_status(result):
    from quant.research_status import status_badge_line

    status = None
    if isinstance(result, list):
        status = next((item.get("research_grade_status") for item in result if isinstance(item, dict) and item.get("research_grade_status")), None)
    elif isinstance(result, dict):
        status = result.get("research_grade_status")
    if status:
        click.echo(f"  {status_badge_line(status)}")


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

@app.command(name="llm-check")
def llm_check():
    """Check whether the configured MiniMax key can complete a tiny request."""
    from quant.decide import check_llm

    result = check_llm()
    if result["ok"]:
        click.echo(f"✅ {result['provider']} {result['model']} is working")
        return

    click.echo(f"❌ {result['provider']} {result['model']} is not usable")
    click.echo(result["message"])
    raise click.exceptions.Exit(1)

@app.command(name="process")
def process():
    """Print the full decision/simulation process."""
    from quant.process import decision_process
    click.echo(decision_process())

@app.command()
@click.option("--tickers", required=True, help="Comma-separated tickers")
@click.option("--from-date", "--from", "start", default="2023-01-01")
@click.option("--to-date", "--to", "end", default="2025-01-01")
@click.option("--strategy", default="sma_cross", type=click.Choice(["sma_cross", "momentum", "buy_hold", "agent"]))
@click.option("--benchmark", default="SPY", help="Benchmark ticker for alpha/beta")
@click.option("--commission-bps", default=0.0, type=float, help="Broker commission in basis points per position change")
@click.option("--slippage-bps", default=2.0, type=float, help="Slippage cost in basis points per position change")
@click.option("--json-output", is_flag=True, help="Emit machine-readable JSON")
def backtest(tickers: str, start: str, end: str, strategy: str, benchmark: str,
             commission_bps: float, slippage_bps: float, json_output: bool):
    """Run backtest over tickers."""
    from quant.backtest import run_backtest
    ticker_list = [t.strip() for t in tickers.split(",")]
    results = run_backtest(
        ticker_list,
        start,
        end,
        strategy=strategy,
        benchmark=benchmark,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    if json_output:
        click.echo(json.dumps(results, indent=2))
        return
    _echo_status(results)
    for r in results:
        if "error" in r:
            click.echo(f"  ⚠️  {r['ticker']}: {r['error']}")
        else:
            click.echo(
                f"  {r['ticker']}: Ret={r['total_return']}%, Sharpe={r['sharpe']}, "
                f"MaxDD={r['max_dd']}%, Alpha={r['alpha']}%, Beta={r['beta']}, "
                f"Trades={r['trades']}, Turnover={r['turnover']}%"
            )

@app.command()
@click.option("--ticker", required=True)
@click.option("--from-date", "--from", "start", default="2020-01-01")
@click.option("--to-date", "--to", "end", default="2025-01-01")
@click.option("--strategy", default="sma_cross", type=click.Choice(["sma_cross", "momentum", "buy_hold", "agent"]))
@click.option("--train-bars", default=252, type=int)
@click.option("--test-bars", default=63, type=int)
@click.option("--benchmark", default="SPY")
@click.option("--json-output", is_flag=True)
def validate(ticker: str, start: str, end: str, strategy: str, train_bars: int,
             test_bars: int, benchmark: str, json_output: bool):
    """Run rolling walk-forward validation."""
    from quant.validation import walk_forward_validate

    result = walk_forward_validate(
        ticker.upper(),
        start,
        end,
        strategy=strategy,
        train_bars=train_bars,
        test_bars=test_bars,
        benchmark=benchmark,
    )
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    if "error" in result:
        click.echo(f"  ⚠️  {result['ticker']}: {result['error']}")
        raise click.exceptions.Exit(1)
    _echo_status(result)
    summary = result["summary"]
    click.echo(
        f"  {result['ticker']} {strategy}: windows={summary['n_valid']}/{summary['n_windows']}, "
        f"median Sharpe={summary['median_sharpe']}, median Ret={summary['median_total_return']}%, "
        f"worst DD={summary['worst_drawdown']}%, positive windows={summary['positive_windows']}%"
    )

@app.command()
@click.option("--tickers", required=True, help="Comma-separated tickers")
@click.option("--from-date", "--from", "start", default="2020-01-01")
@click.option("--to-date", "--to", "end", default="2025-01-01")
@click.option("--method", default="min_variance", type=click.Choice(["equal_weight", "inverse_vol", "risk_parity", "min_variance", "max_sharpe"]))
@click.option("--benchmark", default="SPY")
@click.option("--json-output", is_flag=True)
def optimize(tickers: str, start: str, end: str, method: str, benchmark: str, json_output: bool):
    """Construct a long-only research portfolio."""
    from quant.portfolio import optimize_portfolio

    ticker_list = [t.strip().upper() for t in tickers.split(",")]
    result = optimize_portfolio(ticker_list, start, end, method=method, benchmark=benchmark)
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    if "error" in result:
        click.echo(f"  ⚠️  {result['error']}")
        raise click.exceptions.Exit(1)

    _echo_status(result)
    weights = ", ".join(f"{ticker}={weight:.1%}" for ticker, weight in result["weights"].items())
    metrics = result["metrics"]
    click.echo(
        f"  {method}: {weights} | Sharpe={metrics['sharpe']:.2f}, "
        f"MaxDD={abs(metrics['max_dd']) * 100:.1f}%, Alpha={metrics.get('alpha', 0) * 100:.2f}%"
    )

@app.command(name="decision-audit")
@click.option("--ticker", required=True)
@click.option("--from-date", "--from", "start", default="2018-01-01")
@click.option("--to-date", "--to", "end", default="2025-01-01")
@click.option("--strategy", default="sma_cross", type=click.Choice(["sma_cross", "momentum", "buy_hold", "agent"]))
@click.option("--benchmark", default="SPY")
@click.option("--min-history", default=252, type=int, help="Bars required before the first decision")
@click.option("--horizon", default=21, type=int, help="Forward bars used to judge the decision")
@click.option("--step", default=21, type=int, help="Bars between audited decision dates")
@click.option("--target", default="benchmark", type=click.Choice(["benchmark", "absolute"]))
@click.option("--save-run", is_flag=True, help="Persist a JSON report under runs/")
@click.option("--json-output", is_flag=True)
def decision_audit(ticker: str, start: str, end: str, strategy: str, benchmark: str,
                   min_history: int, horizon: int, step: int, target: str,
                   save_run: bool, json_output: bool):
    """Replay historical BUY/HOLD decisions under a veil-of-ignorance protocol."""
    from quant.audit import audit_historical_decisions

    result = audit_historical_decisions(
        ticker=ticker.upper(),
        start=start,
        end=end,
        strategy=strategy,
        benchmark=benchmark,
        min_history=min_history,
        horizon=horizon,
        step=step,
        target=target,
    )
    saved_path = None
    if save_run and "error" not in result:
        from quant.experiments import save_run as persist_run
        saved_path = persist_run("decision_audit", {
            "ticker": ticker.upper(),
            "start": start,
            "end": end,
            "strategy": strategy,
            "benchmark": benchmark,
            "min_history": min_history,
            "horizon": horizon,
            "step": step,
            "target": target,
        }, result)
        result["saved_run"] = saved_path
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    if "error" in result:
        click.echo(f"  ⚠️  {result['ticker']}: {result['error']}")
        raise click.exceptions.Exit(1)
    _echo_status(result)
    summary = result["summary"]
    click.echo(
        f"  {result['ticker']} {strategy}: decisions={summary['n_decisions']}, "
        f"accuracy={summary['accuracy']}%, Brier={summary['brier_score']}, "
        f"avg edge={summary['avg_decision_edge']}%, avg fwd={summary['avg_forward_return']}%, "
        f"BUY acc={summary['buy_accuracy']}%, HOLD acc={summary['hold_accuracy']}%"
    )
    if saved_path:
        click.echo(f"  saved: {saved_path}")

@app.command(name="decision-audit-batch")
@click.option("--tickers", required=True, help="Comma-separated tickers")
@click.option("--from-date", "--from", "start", default="2018-01-01")
@click.option("--to-date", "--to", "end", default="2025-01-01")
@click.option("--strategy", default="sma_cross", type=click.Choice(["sma_cross", "momentum", "buy_hold", "agent"]))
@click.option("--benchmark", default="SPY")
@click.option("--min-history", default=252, type=int)
@click.option("--horizon", default=21, type=int)
@click.option("--step", default=21, type=int)
@click.option("--target", default="benchmark", type=click.Choice(["benchmark", "absolute"]))
@click.option("--save-run", is_flag=True)
@click.option("--json-output", is_flag=True)
def decision_audit_batch(tickers: str, start: str, end: str, strategy: str, benchmark: str,
                         min_history: int, horizon: int, step: int, target: str,
                         save_run: bool, json_output: bool):
    """Replay historical decisions across a universe under prior-information-only rules."""
    from quant.audit import audit_universe_decisions

    ticker_list = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()]
    result = audit_universe_decisions(
        tickers=ticker_list,
        start=start,
        end=end,
        strategy=strategy,
        benchmark=benchmark,
        min_history=min_history,
        horizon=horizon,
        step=step,
        target=target,
    )
    saved_path = None
    if save_run:
        from quant.experiments import save_run as persist_run
        saved_path = persist_run("decision_audit_batch", {
            "tickers": ticker_list,
            "start": start,
            "end": end,
            "strategy": strategy,
            "benchmark": benchmark,
            "min_history": min_history,
            "horizon": horizon,
            "step": step,
            "target": target,
        }, result)
        result["saved_run"] = saved_path
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    _echo_status(result)
    summary = result["summary"]
    click.echo(
        f"  universe {strategy}: decisions={summary['n_decisions']}, "
        f"accuracy={summary['accuracy']}%, Brier={summary['brier_score']}, "
        f"avg edge={summary['avg_decision_edge']}%"
    )
    for ticker, ticker_summary in result["per_ticker"].items():
        if "error" in ticker_summary:
            click.echo(f"    {ticker}: ⚠️ {ticker_summary['error']}")
        else:
            click.echo(
                f"    {ticker}: n={ticker_summary['n_decisions']}, "
                f"acc={ticker_summary['accuracy']}%, buy_acc={ticker_summary['buy_accuracy']}%, "
                f"hold_acc={ticker_summary['hold_accuracy']}%"
            )
    if saved_path:
        click.echo(f"  saved: {saved_path}")

@app.command(name="paper-sim")
@click.option("--tickers", default="", help="Comma-separated tickers")
@click.option("--universe", default="", help="Point-in-time universe name, e.g. sp500_wikipedia")
@click.option("--from-date", "--from", "start", default="2020-01-01")
@click.option("--to-date", "--to", "end", default="2025-01-01")
@click.option("--strategy", default="momentum", type=click.Choice(["sma_cross", "momentum", "buy_hold", "agent"]))
@click.option("--capital", default=10_000.0, type=float)
@click.option("--monthly-contribution", default=0.0, type=float, help="Cash added before the first rebalance in each month")
@click.option("--benchmark", default="SPY")
@click.option("--min-history", default=252, type=int)
@click.option("--rebalance-step", default=21, type=int)
@click.option("--max-positions", default=5, type=int)
@click.option("--commission-bps", default=0.0, type=float)
@click.option("--slippage-bps", default=2.0, type=float)
@click.option("--max-volume-participation", default=0.05, type=float)
@click.option("--save-run", is_flag=True)
@click.option("--json-output", is_flag=True)
def paper_sim(tickers: str, universe: str, start: str, end: str, strategy: str, capital: float,
              monthly_contribution: float, benchmark: str, min_history: int, rebalance_step: int, max_positions: int,
              commission_bps: float, slippage_bps: float, max_volume_participation: float,
              save_run: bool, json_output: bool):
    """Historically simulate paper money with prior-information-only rebalances."""
    from quant.simulator import simulate_historical_paper

    universe_metadata = None
    if universe:
        from quant.universe import get_universe
        universe_result = get_universe(universe, start)
        ticker_list = universe_result["members"]
        universe_metadata = universe_result["metadata"]
    else:
        ticker_list = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()]
    if not ticker_list:
        raise click.UsageError("Provide --tickers or --universe")
    result = simulate_historical_paper(
        tickers=ticker_list,
        start=start,
        end=end,
        strategy=strategy,
        initial_capital=capital,
        benchmark=benchmark,
        min_history=min_history,
        rebalance_step=rebalance_step,
        max_positions=max_positions,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_volume_participation=max_volume_participation,
        monthly_contribution=monthly_contribution,
    )
    if universe_metadata is not None:
        result["universe"] = {"name": universe, "metadata": universe_metadata, "member_count": len(ticker_list)}
        from quant.research_status import research_grade_status
        result["research_grade_status"] = research_grade_status(
            data_source="yfinance",
            universe_name=universe,
            universe_metadata=universe_metadata,
            validation_method="historical_paper_sim_prior_information",
            has_execution_shortfall=False,
            feature_sources=["price_volume"],
            notes=[
                "Universe metadata is attached, but yfinance bars and execution assumptions remain demo-grade unless vendor-grade inputs are configured.",
            ],
        )
    saved_path = None
    if save_run and "error" not in result:
        from quant.experiments import save_run as persist_run
        saved_path = persist_run("paper_sim", {
            "tickers": ticker_list,
            "start": start,
            "end": end,
            "strategy": strategy,
            "capital": capital,
            "monthly_contribution": monthly_contribution,
            "benchmark": benchmark,
            "min_history": min_history,
            "rebalance_step": rebalance_step,
            "max_positions": max_positions,
            "commission_bps": commission_bps,
            "slippage_bps": slippage_bps,
            "max_volume_participation": max_volume_participation,
            "universe": universe or None,
        }, result)
        result["saved_run"] = saved_path
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    if "error" in result:
        click.echo(f"  ⚠️  {result['error']}")
        raise click.exceptions.Exit(1)
    _echo_status(result)
    metrics = result["metrics"]
    click.echo(
        f"  {strategy}: contributed ${result['total_contributed']:,.2f} -> "
        f"${result['final_equity']:,.2f} "
        f"(profit/contributed={result['profit_on_contributed_capital'] * 100:.2f}%), Sharpe={metrics['sharpe']:.2f}, "
        f"MaxDD={abs(metrics['max_dd']) * 100:.1f}%"
    )
    if result["benchmark_final_equity"] is not None:
        click.echo(
            f"  {result['benchmark']} DCA: contributed ${result['total_contributed']:,.2f} -> "
            f"${result['benchmark_final_equity']:,.2f}"
        )
    if saved_path:
        click.echo(f"  saved: {saved_path}")

@app.command(name="growth-report")
@click.option("--tickers", default="", help="Comma-separated tickers; defaults to the broad research universe")
@click.option("--from-date", "--from", "start", default="2020-01-01")
@click.option("--to-date", "--to", "end", default="2025-01-01")
@click.option("--output", default="", help="HTML output path")
def growth_report(tickers: str, start: str, end: str, output: str):
    """Generate an animated standalone HTML growth chart."""
    from quant.reporting import DEFAULT_UNIVERSE, generate_growth_report

    ticker_list = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()] or DEFAULT_UNIVERSE
    path = generate_growth_report(ticker_list, start=start, end=end, output_path=output or None)
    click.echo(f"✅ Growth report written to {path}")


@app.command(name="workflow-report")
@click.option("--output", default="", help="HTML output path")
def workflow_report(output: str):
    """Generate an HTML report showing the full research workflow and phase status."""
    from quant.reporting import generate_workflow_report

    path = generate_workflow_report(output_path=output or None)
    click.echo(f"✅ Workflow report written to {path}")


@app.command(name="allocate-budget")
@click.option("--capital", required=True, type=float, help="Budget to allocate")
@click.option("--tickers", default="", help="Comma-separated universe; defaults to the allocation cockpit universe")
@click.option("--engine", default="v2", type=click.Choice(["v1", "v2", "both"]))
@click.option("--from-date", "--from", "start", default="2018-01-01")
@click.option("--to-date", "--to", "end", default="2026-05-09")
@click.option("--benchmark", default="SPY")
@click.option("--top-n", default=12, type=int)
@click.option("--strategy", default="momentum", type=click.Choice(["sma_cross", "momentum", "buy_hold", "agent"]))
@click.option("--json-output", is_flag=True)
def allocate_budget(capital: float, tickers: str, engine: str, start: str, end: str,
                    benchmark: str, top_n: int, strategy: str, json_output: bool):
    """Turn a budget into transparent manual IBKR target orders."""
    from quant.allocation_planner import plan_budget_allocation

    ticker_list = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()] or None
    result = plan_budget_allocation(
        capital=capital,
        tickers=ticker_list,
        engine=engine,
        start=start,
        end=end,
        benchmark=benchmark.upper(),
        top_n=top_n,
        strategy=strategy,
    )
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    _echo_status(result)
    click.echo(f"  primary engine: {result['primary_engine']} | budget=${result['capital']:,.2f}")
    for plan in result["plans"]:
        if "error" in plan:
            click.echo(f"  {plan['engine']}: ⚠️ {plan['error']}")
            continue
        allocation = plan["allocation"]
        click.echo(f"  {plan['engine']}: invest=${allocation['deployable_capital']:,.2f}, cash=${allocation['cash']:,.2f}")
        for row in allocation["allocations"]:
            click.echo(
                f"    {row['ticker']}: ${row['allocation']:,.2f} "
                f"({row['shares_at_entry']} sh @ ${row['entry']}) "
                f"stop={row.get('stop', 'n/a')} target={row.get('target', 'n/a')}"
            )


@app.command(name="record-trade")
@click.option("--ticker", required=True)
@click.option("--side", required=True, type=click.Choice(["BUY", "SELL"], case_sensitive=False))
@click.option("--quantity", required=True, type=float)
@click.option("--price", required=True, type=float)
@click.option("--trade-date", required=True)
@click.option("--fees", default=0.0, type=float)
@click.option("--account", default="manual_ibkr")
@click.option("--notes", default="")
@click.option("--json-output", is_flag=True)
def record_trade_cmd(ticker: str, side: str, quantity: float, price: float, trade_date: str,
                     fees: float, account: str, notes: str, json_output: bool):
    """Record a manual IBKR/paper fill in the local Quant Lab journal."""
    from quant.trade_journal import record_trade

    result = record_trade(
        ticker=ticker,
        side=side,
        quantity=quantity,
        price=price,
        trade_date=trade_date,
        fees=fees,
        account=account,
        notes=notes,
    )
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    click.echo(f"✅ Recorded {result['side']} {result['quantity']} {result['ticker']} @ ${result['price']}")


@app.command(name="trades")
@click.option("--limit", default=50, type=int)
@click.option("--json-output", is_flag=True)
def trades(limit: int, json_output: bool):
    """List the local manual trade journal."""
    from quant.trade_journal import list_trades, position_snapshot

    result = {"positions": position_snapshot()["positions"], "trades": list_trades(limit=limit)}
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    if not result["trades"]:
        click.echo("  No recorded trades yet.")
        return
    click.echo("  Positions:")
    for row in result["positions"]:
        click.echo(f"    {row['ticker']}: qty={row['quantity']}, avg_cost=${row['avg_cost']}")
    click.echo("  Recent trades:")
    for row in result["trades"]:
        click.echo(f"    {row['trade_date']} {row['side']} {row['quantity']} {row['ticker']} @ ${row['price']}")


@app.command(name="research-prompt")
@click.option("--as-of", "as_of", default="today")
def research_prompt(as_of: str):
    """Print the exact prompt for manual orthogonal research notes."""
    from quant.orthogonal import manual_research_prompt

    click.echo(manual_research_prompt(as_of))


@app.command(name="record-research")
@click.option("--ticker", required=True)
@click.option("--as-of", "as_of", required=True)
@click.option("--source-type", default="news")
@click.option("--title", required=True)
@click.option("--summary", required=True)
@click.option("--sentiment-score", default=0.0, type=float)
@click.option("--confidence", default=0.5, type=float)
@click.option("--horizon", default="weeks")
@click.option("--published-at", default="")
@click.option("--source-url", default="")
@click.option("--notes", default="")
@click.option("--json-output", is_flag=True)
def record_research(ticker: str, as_of: str, source_type: str, title: str, summary: str,
                    sentiment_score: float, confidence: float, horizon: str,
                    published_at: str, source_url: str, notes: str, json_output: bool):
    """Record timestamped manual orthogonal research context."""
    from quant.orthogonal import record_research_note

    result = record_research_note(
        ticker=ticker,
        as_of=as_of,
        source_type=source_type,
        title=title,
        summary=summary,
        sentiment_score=sentiment_score,
        confidence=confidence,
        horizon=horizon,
        published_at=published_at,
        source_url=source_url,
        notes=notes,
    )
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    click.echo(f"✅ Recorded research note {result['id']} for {result['ticker']}")


@click.group()
def norgate():
    """Norgate Data import and status commands."""
    pass


app.add_command(norgate)


@norgate.command(name="status")
@click.option("--json-output", is_flag=True)
def norgate_status(json_output: bool):
    """Show local Norgate import status."""
    from quant.norgate import status

    result = status()
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    click.echo(f"  db: {result['db_path']}")
    click.echo(f"  imported tickers: {result['ticker_count']} | rows: {result['rows']}")
    for row in result["items"][:20]:
        click.echo(f"    {row['market']} {row['ticker']}: {row['rows']} rows {row['first_date']} -> {row['last_date']}")
    if len(result["items"]) > 20:
        click.echo(f"    ... {len(result['items']) - 20} more")
    click.echo("  limitations:")
    for item in result["limitations"]:
        click.echo(f"    - {item}")


@norgate.command(name="import-ascii")
@click.option("--path", "path_", required=True, help="Folder containing Norgate ASCII/CSV exports")
@click.option("--market", default="", help="Optional market label: US, CA, AU")
@click.option("--append", "append_", is_flag=True, help="Append without deleting prior rows for each ticker/market")
@click.option("--json-output", is_flag=True)
def norgate_import_ascii(path_: str, market: str, append_: bool, json_output: bool):
    """Import Norgate ASCII/CSV OHLCV exports into the local cache."""
    from quant.norgate import import_ascii_directory

    result = import_ascii_directory(path_, market=market, overwrite=not append_)
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    click.echo(
        f"  imported {result['rows_imported']} rows from {result['files_imported']}/{result['files_seen']} files "
        f"for {len(result['tickers'])} tickers"
    )
    click.echo("  To use this data source for engines:")
    click.echo("    export QUANT_DATA_SOURCE=norgate")
    if market:
        click.echo(f"    export QUANT_NORGATE_MARKET={market.upper()}")


@norgate.command(name="import-metadata")
@click.option("--path", "path_", required=True, help="Folder containing Windows bridge metadata export")
@click.option("--append", "append_", is_flag=True, help="Append without deleting prior metadata rows")
@click.option("--json-output", is_flag=True)
def norgate_import_metadata(path_: str, append_: bool, json_output: bool):
    """Import Norgate security-master/constituent metadata exported from Windows."""
    from quant.norgate import import_metadata_directory

    result = import_metadata_directory(path_, overwrite=not append_)
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    click.echo(
        f"  imported security_master={result['security_master_rows']} "
        f"constituent_rows={result['constituent_rows']}"
    )


@norgate.command(name="test")
@click.option("--ticker", required=True)
@click.option("--from-date", "--from", "start", default="2024-01-01")
@click.option("--to-date", "--to", "end", default="2026-05-09")
@click.option("--market", default="")
@click.option("--json-output", is_flag=True)
def norgate_test(ticker: str, start: str, end: str, market: str, json_output: bool):
    """Read imported Norgate bars for one ticker."""
    from quant.norgate import fetch_bars_from_cache

    bars = fetch_bars_from_cache(ticker.upper(), start, end, market=market)
    result = {
        "ticker": ticker.upper(),
        "market": market.upper() or "any",
        "start": start,
        "end": end,
        "rows": len(bars),
        "first": bars[0] if bars else None,
        "last": bars[-1] if bars else None,
    }
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    if not bars:
        click.echo(f"  No imported Norgate rows for {ticker.upper()} in that range.")
        raise click.exceptions.Exit(1)
    click.echo(f"  {ticker.upper()}: {len(bars)} rows | first={bars[0]} | last={bars[-1]}")


@norgate.command(name="write-windows-bridge")
@click.option("--output", default="scripts/norgate_windows_export.py")
def norgate_write_windows_bridge(output: str):
    """Write a Windows-side Norgate Python export bridge script."""
    from quant.norgate import write_windows_bridge

    path = write_windows_bridge(output)
    click.echo(f"✅ Wrote Windows Norgate export bridge to {path}")


@norgate.command(name="survivorship-sim")
@click.option("--market", default="US", help="Imported Norgate market label")
@click.option("--from-date", "--from", "start", default="2024-05-09")
@click.option("--to-date", "--to", "end", default="2026-05-09")
@click.option("--capital", default=20_000.0, type=float)
@click.option("--lookback", default=63, type=int)
@click.option("--min-history", default=126, type=int)
@click.option("--rebalance-step", default=21, type=int)
@click.option("--max-positions", default=10, type=int)
@click.option("--min-price", default=5.0, type=float)
@click.option("--min-dollar-volume", default=5_000_000.0, type=float)
@click.option("--commission-bps", default=0.0, type=float)
@click.option("--slippage-bps", default=2.0, type=float)
@click.option("--max-volume-participation", default=0.025, type=float)
@click.option("--benchmark", default="SPY")
@click.option("--universe", default="common_stock", type=click.Choice(["common_stock", "all"]))
@click.option("--exchanges", default="NYSE,Nasdaq,NYSE American", help="Comma-separated exchange filter; empty means all imported exchanges")
@click.option("--json-output", is_flag=True)
def norgate_survivorship_sim(
    market: str,
    start: str,
    end: str,
    capital: float,
    lookback: int,
    min_history: int,
    rebalance_step: int,
    max_positions: int,
    min_price: float,
    min_dollar_volume: float,
    commission_bps: float,
    slippage_bps: float,
    max_volume_participation: float,
    benchmark: str,
    universe: str,
    exchanges: str,
    json_output: bool,
):
    """Run a Norgate PIT active/delisted-universe simulation."""
    from quant.norgate_simulator import simulate_norgate_survivorship

    result = simulate_norgate_survivorship(
        market=market,
        start=start,
        end=end,
        initial_capital=capital,
        lookback=lookback,
        min_history=min_history,
        rebalance_step=rebalance_step,
        max_positions=max_positions,
        min_price=min_price,
        min_dollar_volume=min_dollar_volume,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        max_volume_participation=max_volume_participation,
        benchmark=benchmark.upper(),
        universe=universe,
        exchanges=[item.strip() for item in exchanges.split(",") if item.strip()] or None,
    )
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return
    if "error" in result:
        click.echo(f"  ⚠️ {result['error']}")
        raise click.exceptions.Exit(1)
    _echo_status(result)
    metrics = result["metrics"]
    click.echo(
        f"  Norgate {result['market']} {universe}: ${result['initial_capital']:,.2f} -> "
        f"${result['final_equity']:,.2f} ({result['total_return_pct']}%), "
        f"Sharpe={metrics['sharpe']:.2f}, MaxDD={abs(metrics['max_dd']) * 100:.1f}%"
    )
    if result["benchmark_final_equity"] is not None:
        click.echo(
            f"  {result['benchmark']}: ${result['initial_capital']:,.2f} -> "
            f"${result['benchmark_final_equity']:,.2f} ({result['benchmark_total_return_pct']}%)"
        )
    click.echo(
        f"  universe={result['n_securities']} securities, loaded_series={result['n_loaded_price_series']}, "
        f"ended/delisted={result['n_delisted_or_ended_securities']}, rebalances={result['n_rebalances']}"
    )


@app.command(name="web")
@click.option("--host", default="127.0.0.1", help="Host interface; keep 127.0.0.1 for local-only use")
@click.option("--port", default=8765, type=int, help="Port for the local web app")
@click.option("--no-open", is_flag=True, help="Do not open the browser automatically")
def web(host: str, port: int, no_open: bool):
    """Run the local browser interface for Quant Lab."""
    from quant.webapp import run_web_app

    run_web_app(host=host, port=port, open_browser=not no_open)

@app.command(name="recommend-v2")
@click.option("--tickers", default="", help="Comma-separated universe; defaults to liquid research universe")
@click.option("--from-date", "--from", "start", default="2016-01-01")
@click.option("--to-date", "--to", "end", default="2026-05-09")
@click.option("--benchmark", default="SPY")
@click.option("--horizon", default=63, type=int)
@click.option("--top-n", default=10, type=int)
@click.option("--json-output", is_flag=True)
def recommend_v2(tickers: str, start: str, end: str, benchmark: str, horizon: int, top_n: int, json_output: bool):
    """Run calibrated technical recommendation engine."""
    from quant.technical_v2 import DEFAULT_RECOMMENDATION_UNIVERSE, latest_recommendations

    ticker_list = [ticker.strip().upper() for ticker in tickers.split(",") if ticker.strip()]
    if not ticker_list:
        ticker_list = DEFAULT_RECOMMENDATION_UNIVERSE
    result = latest_recommendations(
        ticker_list,
        start=start,
        end=end,
        benchmark=benchmark.upper(),
        horizon=horizon,
        top_n=top_n,
    )
    if json_output:
        click.echo(json.dumps(result, indent=2))
        return

    _echo_status(result)
    validation = result["validation"]
    click.echo(
        f"  calibrated technical v2: samples={result['audit']['n_calibration_samples']}, "
        f"folds={validation.get('n_folds', 0)}, "
        f"top-quintile active={validation.get('avg_top_quintile_active_return', 0) * 100:.2f}%"
    )
    for item in result["recommendations"]:
        pullback = item["pullback_plan"]
        breakout = item["breakout_plan"]
        gates = item["gates"]
        click.echo(
            f"  {item['ticker']}: pred_active={item['predicted_63d_active_return'] * 100:.2f}%, "
            f"rank={item['rank_score'] * 100:.2f}%, price=${item['price']:.2f}, "
            f"pullback=${pullback['entry']:.2f}/stop=${pullback['stop']:.2f}, "
            f"breakout=${breakout['entry']:.2f}/stop=${breakout['stop']:.2f}, "
            f"weekly={gates['weekly_trend']}, ADX={gates['trend_strength']}, "
            f"volume_breakout={gates['volume_confirmed_breakout']}"
        )

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
