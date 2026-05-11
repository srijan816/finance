# Research-Grade Quant Lab Roadmap

## North Star

This project should become a reproducible research workbench, not an autonomous trading bot. A top-tier financial company would expect every result to carry data provenance, assumptions, benchmark-relative metrics, transaction-cost modeling, validation methodology, and enough audit trail to reproduce the conclusion later.

## Open-Source Mechanisms To Leverage

- **QuantConnect LEAN**: institutional-grade event-driven simulation and live-trading engine. Best future target when this project needs multi-asset event simulation, corporate actions, brokerage models, and production deployment semantics.
- **vectorbt**: fast vectorized research and parameter sweeps. Best for notebook-scale strategy exploration and factor sweeps.
- **PyPortfolioOpt / Riskfolio-Lib / skfolio**: portfolio construction, covariance/risk estimators, Black-Litterman, HRP, downside-risk and constrained optimization.
- **Empyrical-style metrics**: standardized risk and attribution metrics such as Sharpe, Sortino, Calmar, drawdown, alpha, beta, and tail risk.
- **Purged or walk-forward validation**: time-series validation that prevents lookahead and leakage from future labels.

## Implemented In This Pass

- Explicit MiniMax diagnostic command: `quant llm-check`.
- Lookahead-safe daily signal lag in backtests.
- Commission and slippage assumptions in basis points.
- Benchmark-relative alpha, beta, information ratio, and benchmark return.
- Tail-risk and drawdown metrics: VaR, CVaR, max drawdown, Calmar.
- Exposure, turnover, trade count, final equity, annual return, annual volatility.
- Walk-forward validation command: `quant validate`.
- Long-only portfolio construction command: `quant optimize`.
- Equal-weight, inverse-volatility/risk-parity, minimum-variance, and max-Sharpe allocation methods.
- Historical decision quality audit: `quant decision-audit` and `quant decision-audit-batch`.
- Veil-of-ignorance protocol: decisions use only prior bars, enter on the next bar, and score future absolute or benchmark-relative returns.
- Statistical edge diagnostics: binomial p-values, bootstrap confidence intervals, and mean-edge p-values.
- Point-in-time news store: historical news must be filtered by `published_at <= decision_time` before it can be used in any simulated decision.
- JSON experiment registry under `runs/` for saved research reports.
- Deterministic unit tests for metrics, backtesting, CLI validation, and data parsing.

## Next Upgrades

1. **Data provenance layer**
   Store source, fetch timestamp, adjustment mode, ticker universe definition, missing-data decisions, and raw-vs-adjusted prices.

2. **Corporate actions and survivorship controls**
   Use a vendor or dataset that exposes delistings, splits, dividends, symbol history, and point-in-time universes. Yahoo is fine for demos, not institutional research.

3. **Portfolio optimizer**
   Add PyPortfolioOpt or Riskfolio-Lib adapters for HRP, min-vol, max-Sharpe, Black-Litterman, max diversification, and CVaR portfolios.

4. **Engine adapter boundary**
   Keep this vectorized engine for fast research, then add a LEAN adapter for event-driven confirmation before any strategy is considered deployable.

5. **Leakage-aware ML validation**
   Add purged/embargoed cross-validation for models whose labels overlap in time, especially event-driven labels or multi-day forward returns.

6. **Experiment registry**
   Persist every run's code version, parameters, universe, data hash, metrics, plots, and output files.

7. **Risk and compliance controls**
   Position limits, drawdown stops, sector caps, liquidity filters, borrow constraints, restricted-list checks, and pre-trade checks before paper or live execution.

8. **LLM governance**
   Treat the LLM as an explanation and hypothesis assistant, not a source of truth. Require structured JSON, prompt versioning, citations to data, confidence calibration, and no-trade fallback when data quality is weak.

9. **News and text data**
   Add a licensed historical news provider with immutable publication timestamps. News features must be joined point-in-time, after publication and before the simulated decision cutoff. LLM sentiment over old articles must use only article text, not the model's memorized knowledge of what happened afterward.

10. **Multiple-testing controls**
   Track the number of tried universes, horizons, strategies, filters, and parameters. Use White's Reality Check, Hansen SPA, Deflated Sharpe Ratio, or similar corrections before promoting any result.
