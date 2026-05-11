# Quant Lab

Personal Quant Research Lab — local browser app and CLI for multi-agent stock intelligence, backtesting, validation, portfolio construction, and LLM-assisted analysis.

## Install

```bash
# Clone/setup venv
python3.11 -m venv .venv
source .venv/bin/activate  # or .venv/bin/activate.fish

# Install main package
.venv/bin/pip install -e .

# Optional: portfolio research libraries for future optimizer adapters
.venv/bin/pip install -e ".[research,dev]"

# Optional: TradingAgents dependency (for full multi-agent pipeline)
.venv/bin/pip install ./upstream/TradingAgents/
```

## Configure

Create a `.env` file for optional features:

```env
# Required for paper trading (Alpaca)
ALPACA_KEY=your_key_here
ALPACA_SECRET=your_secret_here

# Optional: MiniMax LLM backend
MINIMAX_API_KEY=your_key_here
```

## Commands

### Web App
```bash
quant web
```
Opens the local browser interface at `http://127.0.0.1:8765`. The web app is the main guided interface: it explains each workflow, shows the exact command it will run, executes allowlisted Quant Lab actions, streams progress/output, and displays research-grade status so demo-grade results are not mistaken for production evidence. Actions are grouped into Portfolio, Research, Diagnostics, Understand, Reports, and System tabs.

### Budget Allocation Cockpit
```bash
quant allocate-budget --capital 20000 --engine v2 --json-output
quant allocate-budget --capital 20000 --engine both --tickers SPY,QQQ,AAPL,MSFT,NVDA,GOOGL,AMZN,META,AVGO,AMD,TXN,AMAT,CAT,CSCO,XLK
```
Turns a budget into a transparent target allocation table with target notional, estimated shares, entry reference, stop reference, target reference, cash reserve, manual IBKR setup steps, and scenario expectation paths. V2 is the preferred engine because it has calibrated active-return estimates; V1 is shown as a deterministic baseline when requested.

### Manual Trade Journal
```bash
quant record-trade --ticker AAPL --side BUY --quantity 3 --price 200 --trade-date 2026-05-09 --fees 1
quant trades
```
Record fills after manually copying targets into IBKR. The allocation cockpit compares recorded positions against the current target plan so the app can track intended vs actual exposure while broker automation remains gated.

### Manual Orthogonal Research
```bash
quant research-prompt --as-of 2026-05-09
quant record-research --ticker NVDA --as-of 2026-05-09 --source-type news --title "Source title" --summary "Timestamped facts only" --sentiment-score 0.2 --confidence 0.7
```
Stores timestamped news/fundamental/flow notes in a local SQLite research notebook. These notes are visible as decision context but are not promoted into model features until point-in-time validation and leakage controls are strong enough.

### Norgate Data
```bash
quant norgate status
quant norgate import-ascii --path /path/to/norgate/export --market US
quant norgate import-metadata --path /path/to/windows/bridge/export
quant norgate survivorship-sim --market US --from-date 2024-05-09 --to-date 2026-05-09 --max-positions 50 --min-price 10 --min-dollar-volume 100000000
export QUANT_DATA_SOURCE=norgate
quant recommend-v2 --tickers AAPL,MSFT,NVDA --from-date 2024-01-01 --to-date 2026-05-09
```
On macOS, Quant Lab consumes Norgate via ASCII/CSV exports. Put exported files under `data/norgate/ascii/` or point `quant norgate import-ascii` at the export folder. The importer accepts common OHLCV headers such as `Date,Open,High,Low,Close,Volume`.

`quant norgate survivorship-sim` is the broad-universe sanity check: it uses imported Norgate security-master active dates plus delisted/ended symbols, ranks only securities active on each rebalance date, and compares the resulting portfolio with `SPY`. This is the preferred way to test whether a signal survives outside the hand-picked current watchlist.

For full Norgate Python API access, use Windows or a Windows VM with Norgate Data Updater installed and logged in:

```bash
quant norgate write-windows-bridge
```

Copy `scripts/norgate_windows_export.py` to Windows, run it there, then copy the exported folder back to this machine and import it. The Mac ASCII path is daily price data only; richer point-in-time index membership, delisted/security-master metadata, and fundamentals need the Windows API/export bridge.

### Backtest
```bash
quant backtest --tickers NVDA,AAPL --from-date 2024-01-01 --to-date 2025-01-01 --strategy sma_cross
quant backtest --tickers NVDA --from-date 2020-01-01 --to-date 2025-01-01 --commission-bps 0 --slippage-bps 2 --json-output
```
Runs a lookahead-safe daily backtest. Outputs return, Sharpe, max drawdown, alpha/beta vs benchmark, turnover, trade count, VaR/CVaR, and explicit assumptions.

### Walk-Forward Validation
```bash
quant validate --ticker NVDA --from-date 2020-01-01 --to-date 2025-01-01 --strategy momentum
```
Runs rolling out-of-sample validation windows to reduce overfit and regime-dependence risk.

### Portfolio Optimization
```bash
quant optimize --tickers NVDA,AAPL,MSFT,SPY --from-date 2020-01-01 --to-date 2025-01-01 --method min_variance
quant optimize --tickers NVDA,AAPL,MSFT,SPY --method risk_parity --json-output
```
Constructs a long-only research portfolio using equal weight, inverse volatility/risk parity, minimum variance, or max-Sharpe allocation.

### Decision Audit
```bash
quant decision-audit --ticker NVDA --from-date 2018-01-01 --to-date 2025-01-01 --strategy momentum --horizon 21 --step 21
quant decision-audit --ticker NVDA --strategy sma_cross --target absolute --save-run --json-output
quant decision-audit-batch --tickers NVDA,AAPL,MSFT,GOOGL,TSLA --strategy momentum --save-run
```
Replays historical BUY/HOLD decisions under a veil-of-ignorance protocol: each decision uses only prior bars, enters on the next bar, and is judged on future returns.
Reports accuracy, Brier score, decision-edge confidence intervals, and p-values so small edges are not over-interpreted.

### Historical Paper Simulation
```bash
quant paper-sim --tickers NVDA,AAPL,MSFT,GOOGL,TSLA --from-date 2020-01-01 --to-date 2025-01-01 --strategy momentum --capital 10000 --save-run
quant paper-sim --universe sp500_wikipedia --from-date 2023-01-01 --to-date 2025-01-01 --strategy momentum --capital 10000 --max-volume-participation 0.025 --save-run
```
Simulates paper money with prior-information-only monthly rebalances, equal-weight allocation across BUY signals, explicit cash, zero default broker commission, slippage, volume participation caps, fills/rejections, and SPY benchmark comparison.

### Analyze
```bash
quant analyze NVDA
quant analyze NVDA --date 2025-01-15
```
LLM-powered stock analysis using MiniMax M2.7. If MiniMax is missing or rejected, the command reports analysis unavailable and does not fabricate a trading decision.

### LLM Check
```bash
quant llm-check
```
Runs a tiny MiniMax request and prints whether the configured key is usable.

### Decision Process
```bash
quant process
```
Prints the current end-to-end decision and simulation process, including data ingestion, universe selection, signal formation, veil-of-ignorance rules, execution model, and production caveats.

### Calibrated Technical Recommendations
```bash
quant recommend-v2 --tickers SPY,QQQ,NVDA,AVGO,AMAT --from-date 2018-01-01 --to-date 2026-05-09 --top-n 5
quant recommend-v2 --json-output
```
Runs the calibrated technical V2 engine: transparent feature extraction, weekly confirmation, ADX/MA-slope trend strength, relative-volume breakout confirmation, RSI divergence flags, regime-aware ATR stops, and walk-forward validation.

### Workflow UI
```bash
quant workflow-report
```
Writes `reports/workflow.html`, a visible phase-by-phase map of what the app is doing, which controls are implemented, and which items remain blocked by external data or live validation.

### Morning Briefing
```bash
quant brief
quant brief --tickers NVDA,AAPL,MSFT
```
Generates `briefings/YYYY-MM-DD.md` with analysis for each watchlist ticker.

### Paper Trading
```bash
quant paper status        # Check Alpaca account
quant paper buy NVDA 10   # Market buy 10 shares
quant paper sell NVDA 5   # Market sell 5 shares
```
Requires `ALPACA_KEY` and `ALPACA_SECRET` in `.env`.

### Self-Improvement
```bash
quant improve --ticker NVDA --days 30
```
Reviews recent decisions from `data/decisions.db`, fetches realized returns, and critiques via LLM.

## Architecture

```
quant/
  cli.py        — Click CLI entry points
  data.py       — yfinance data fetch + SQLite cache (data/quotes.db)
  norgate.py    — Norgate ASCII import/cache plus Windows API export bridge script
  audit.py      — historical decision quality and calibration audits
  news.py       — point-in-time historical news filtering
  stats.py      — bootstrap intervals, z-tests, and binomial p-values
  decide.py     — MiniMax LLM wrapper that fails closed when unavailable
  execution.py  — broker simulator with fills, fees, slippage, and volume caps
  backtest.py   — lookahead-safe daily backtest harness
  metrics.py    — performance, attribution, drawdown, and tail-risk metrics
  experiments.py — JSON run registry for reproducible research outputs
  portfolio.py  — long-only research portfolio construction
  allocation_planner.py — budget-to-target allocation cockpit
  trade_journal.py — manual IBKR/paper trade journal and target comparison
  orthogonal.py — timestamped manual research notes and prompt
  simulator.py  — historical paper-money portfolio simulation
  universe.py   — point-in-time universe provider adapters
  process.py    — documented decision-process report
  workflow.py   — visible workflow and phase status for UI reports
  webapp.py     — local browser UI and allowlisted workflow runner
  recommendations.py — entry-specific stop/target helpers
  technical_v2.py — calibrated technical recommendation engine
  strategies.py — deterministic research signals
  validation.py — walk-forward validation
  paper.py      — Alpaca paper trading client
  briefing.py   — Morning briefing generator
  critic.py     — Decision journal + self-improvement loop (data/decisions.db)
```

- **Data**: yfinance for OHLCV, SQLite for caching
- **Norgate Data**: optional imported ASCII/CSV OHLCV cache selected with `QUANT_DATA_SOURCE=norgate`
- **Analysis**: Direct LLM calls to MiniMax's Anthropic-compatible endpoint, with MiniMax OpenAI-compatible fallback
- **Backtesting**: lookahead-safe daily simulation with costs, slippage, benchmark-relative metrics, and tail risk
- **Validation**: rolling walk-forward windows for out-of-sample sanity checks
- **Decision Audits**: historical BUY/HOLD quality, calibration, and forward-return scoring under prior-information-only rules
- **Research Status**: every major output carries a DEMO / RESEARCH / PRODUCTION_CANDIDATE status block
- **Allocation Cockpit**: budget-to-target order plan, manual IBKR instructions, expectation scenarios, and target-vs-recorded comparison
- **Manual Tracking**: local trade journal for real/paper fills copied from broker screens
- **Orthogonal Notes**: point-in-time manual research capture for news, filings, analyst revisions, macro, and flow context
- **Universe Selection**: custom point-in-time CSV universes, plus a real Wikipedia S&P 500 adapter with explicit survivorship-bias warnings
- **Execution Simulation**: cash ledger, share positions, zero default broker commission, slippage, partial fills, rejected orders, and volume participation limits
- **Paper Trading**: Alpaca paper API (real execution, zero risk)
- **Decision Journal**: SQLite at `data/decisions.db` — stores all analysis decisions for review

## Limitations

- **No real money**: Paper trading only. Alpaca keys default to paper API.
- **No mock LLM decisions**: `quant analyze` fails closed without a working `MINIMAX_API_KEY`; it does not invent `BUY/HOLD/SELL` output.
- **Not financial advice**: This is a research system. Backtested results ≠ future performance.
- **No trading agent autonomy**: Orders must be manually triggered via `quant paper buy/sell`.
- **Manual IBKR only for now**: The app can produce target orders and record fills, but it does not connect to or trade through IBKR yet.
- **Expectation graphs are scenarios**: They compound the current model-implied edge mechanically and are not promises or guaranteed profit forecasts.
- **Incomplete upstream**: `upstream/TradingAgents/` is vendored but not wired into the main analysis pipeline.
- **Data quality**: Yahoo Finance and public Wikipedia data are useful for transparent research, not institutional point-in-time production. Vendor data such as CRSP/Norgate is still required for survivorship-bias-free institutional testing.
- **Norgate on Mac is partial**: ASCII exports give daily price bars; full Norgate metadata requires Windows/Norgate Data Updater and a bridge export.

## Test

```bash
pytest tests/ -v
```
