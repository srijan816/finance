# Quant Lab

Personal Quant Research Lab — multi-agent stock intelligence CLI powered by LLMs and vectorbt.

## Install

```bash
# Clone/setup venv
python3.11 -m venv .venv
source .venv/bin/activate  # or .venv/bin/activate.fish

# Install main package
.venv/bin/pip install -e .

# Optional: TradingAgents dependency (for full multi-agent pipeline)
.venv/bin/pip install ./upstream/TradingAgents/
```

## Configure

Create a `.env` file for optional features:

```env
# Required for paper trading (Alpaca)
ALPACA_KEY=your_key_here
ALPACA_SECRET=your_secret_here

# Optional: LLM backends (falls back to mock without these)
MINIMAX_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here
```

## Commands

### Backtest
```bash
quant backtest --tickers NVDA,AAPL --from-date 2024-01-01 --to-date 2025-01-01
```
Runs vectorbt-powered backtest. Outputs Sharpe ratio, max drawdown, and win rate per ticker.

### Analyze
```bash
quant analyze NVDA
quant analyze NVDA --date 2025-01-15
```
LLM-powered stock analysis (MiniMax via OpenRouter). Falls back to mock response if no API key.

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
  decide.py     — LLM wrapper (MiniMax/OpenRouter) + mock fallback
  backtest.py   — vectorbt backtest harness
  paper.py      — Alpaca paper trading client
  briefing.py   — Morning briefing generator
  critic.py     — Decision journal + self-improvement loop (data/decisions.db)
```

- **Data**: yfinance for OHLCV, SQLite for caching
- **Analysis**: Direct LLM calls (MiniMax/OpenRouter); falls back to mock without API keys
- **Backtesting**: vectorbt for performance metrics
- **Paper Trading**: Alpaca paper API (real execution, zero risk)
- **Decision Journal**: SQLite at `data/decisions.db` — stores all analysis decisions for review

## Limitations

- **No real money**: Paper trading only. Alpaca keys default to paper API.
- **Mock LLM without keys**: `quant analyze` returns mock `HOLD` decisions without `MINIMAX_API_KEY` or `OPENROUTER_API_KEY`.
- **Not financial advice**: This is a research toy. Backtested results ≠ future performance.
- **No trading agent autonomy**: Orders must be manually triggered via `quant paper buy/sell`.
- **Incomplete upstream**: `upstream/TradingAgents/` is vendored but not wired into the main analysis pipeline.

## Test

```bash
pytest tests/ -v
```
