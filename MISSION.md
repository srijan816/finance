# Quant Lab — Mission (rewritten from briefing)

## Deliverable
Build a research-grade, paper-trading-ready stock intelligence system on top of TauricResearch/TradingAgents (v0.2.4). By morning:
1. `quant analyze NVDA` → multi-agent firm-style decision report with BUY/HOLD/SELL + confidence
2. `quant backtest --from 2023-01-01 --to 2025-01-01` → real Sharpe/max-Drawdown/win-rate table
3. `quant paper buy NVDA 10` → executes on Alpaca paper (paper-api.alpaca.markets only)
4. `quant brief` → morning briefing markdown for watchlist [NVDA, AAPL, MSFT, GOOGL, TSLA]
5. Self-improvement loop: critic.py walks past decisions, fetches realized returns, proposes prompt edits

## Success Criteria (S1–S12)
- S1: pip install -e . works in fresh venv
- S2: pytest -x ≥85% green, zero crashes
- S3: quant analyze NVDA → real markdown report with Bull/Bear debate + BUY/HOLD/SELL
- S4: quant backtest → real numeric Sharpe, max-DD, win-rate
- S5: quant paper → Alpaca paper connection (graceful skip if no keys)
- S6: quant brief → morning briefing markdown
- S7: ≥5 self-improvement cycles with prompt version evolution
- S8: Beautiful Rich UI: colored verdicts, progress bars, no raw dicts
- S9: README <5min install + first run + limitations disclaimer
- S10: ≥6 skills in ~/.hermes/skills/
- S11: ≥15 git commits
- S12: MORNING_REPORT.md follows template

## 12-Step Plan
1. Install TradingAgents + dependencies in venv; verify import works
2. Configure MiniMax M2.7 via OpenRouter; test single decision for NVDA
3. Scaffold quant/ package: __init__.py, cli.py (Typer), decide.py
4. Build data.py: yfinance + SQLite cache + unified Bar/Quote schema
5. Build backtest.py: vectorbt harness → Sharpe, max DD, win rate vs SPY
6. Build paper.py: Alpaca paper client with graceful key-missing handling
7. Build briefing.py: daily brief for watchlist → markdown in briefings/
8. Build critic.py + ui.py: self-improvement loop + Rich terminal UI
9. Write test suite: test_data, test_decide (mock LLM), test_backtest, test_paper, test_cli
10. First real run: quant analyze NVDA end-to-end
11. Self-improvement loop on 5+ historical decisions (2024 data)
12. README + Morning Report + skill creation + cron registration

## Architecture
```
quant-lab/
├── upstream/TradingAgents/   # git clone, never modify
├── quant/                   # MY package
│   ├── cli.py               # Typer: analyze, backtest, paper, brief, improve
│   ├── decide.py            # Wraps TradingAgentsGraph + OpenRouter/MiniMax
│   ├── data.py              # yfinance + cache
│   ├── backtest.py          # vectorbt → metrics
│   ├── paper.py            # Alpaca paper client
│   ├── briefing.py          # Daily watchlist brief
│   ├── critic.py           # Self-improvement loop
│   └── ui.py               # Rich tables + colored verdicts
├── prompts/                 # versioned prompt templates
├── tests/
├── data/                   # SQLite caches
├── briefings/             # daily briefs
└── reports/               # analysis reports
```
