# Quant Lab Audit Validity And Fix Plan

Date: 2026-05-09

Scope: This file checks the external audit against the actual `quant-lab` codebase and public methodology references, then lays out a production-grade repair plan. It is an engineering/research-methodology review, not financial advice.

## Executive Verdict

The audit is mostly valid. I would not treat the existing headline results as proof of trading edge. The code is a serious research prototype, but the current V2 recommendation path is not yet research-grade enough for capital allocation without stronger data provenance, leakage-aware validation, unbiased universes, factor diagnostics, risk-aware allocation, and execution realism.

Most important finding: the app already documents some of its limits honestly, and several modules are pointed in the right direction. But the current workflow still allows exactly the kinds of inflated confidence the audit warns about.

## Public References Used To Cross-Check The Audit

- [CRSP US Stock Databases](https://www.crsp.org/research/crsp-us-stock-databases/) describe survivor-bias-free stock history, active and inactive securities, permanent identifiers, corporate actions, delisting information, and rigorous longitudinal research use.
- [Norgate Data FAQ](https://norgatedata.com/data-package-faq.php) explains why historical constituent membership is not just a raw ticker list problem, because symbols and companies change over time.
- [Norgate Data content tables](https://norgatedata.com/data-content-tables.php) document extensive delisted-security coverage and historical major-exchange listing identification.
- [Bailey and Lopez de Prado, Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) explicitly addresses selection bias, multiple testing, non-normal returns, and inflated Sharpe ratios.
- [Bailey, Borwein, Lopez de Prado, and Zhu, Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253) proposes a framework to estimate backtest overfitting in investment simulations.
- [Purged cross-validation overview](https://en.wikipedia.org/wiki/Purged_cross-validation) is not my preferred primary source, but it cleanly summarizes the leakage issue when labels depend on future windows, plus purge, embargo, and CPCV.
- [Alphalens Reloaded documentation](https://alphalens.ml4trading.io/) frames factor research around returns analysis, information coefficient analysis, turnover analysis, and group analysis.
- [Alphalens API reference](https://alphalens.ml4trading.io/api-reference.html) defines Spearman IC, mean return by quantile, quantile turnover, group-adjusted analysis, and long-short/group-neutral diagnostics.
- [PyPortfolioOpt documentation](https://pyportfolioopt.readthedocs.io/en/latest/index.html) supports covariance/risk-model based portfolio optimization, shrinkage, Black-Litterman, HRP, and risk-efficient alpha combination.
- [PyPortfolioOpt mean-variance docs](https://pyportfolioopt.readthedocs.io/en/latest/MeanVariance.html) show efficient frontier inputs, covariance matrices, constraints, objectives, transaction-cost objective terms, and tracking error objectives.
- [yfinance documentation](https://ranaroussi.github.io/yfinance/index.html) says yfinance is research/educational, not affiliated with Yahoo, and Yahoo Finance API use is intended for personal use.

I did not independently verify the audit's claims about proprietary internal practices at Renaissance, Two Sigma, D.E. Shaw, Citadel, Millennium, or Barclays. Those are not necessary to validate the app-level criticisms. The methodology criticisms stand on public literature and this repository's code.

## Validity Matrix

| Audit claim | Verdict | Severity | Code evidence | Notes |
|---|---:|---:|---|---|
| Default universe has survivorship/current-winner bias | Valid | Critical | `quant/technical_v2.py:18-25` | `DEFAULT_RECOMMENDATION_UNIVERSE` is a hand-picked current liquid list. This makes historical backtests over earlier years suspect. |
| Data source is yfinance/Yahoo, not institutional/PIT data | Valid | High | `quant/data.py:1-67`, `README.md:147` | Useful for research demos, not sufficient for production claims. yfinance itself states research/educational intent. |
| Walk-forward validation lacks explicit purge/embargo/CPCV/PBO/DSR | Valid | Critical | `quant/technical_v2.py:217-295`, `quant/validation.py:1-69` | V2 labels are forward 63-day returns; validation sorts by sample date and slices train/test without purging overlapping label windows. |
| V2 uses only price/volume technical features | Valid | High | `quant/technical_v2.py:27-49`, `quant/technical_v2.py:81-122` | Features are momentum, moving averages, RSI, ATR, ADX/DI, volume, breakout pressure, weekly trend, and divergence. No fundamentals, sentiment, flow, macro, or analyst revisions. |
| Features are globally standardized, not cross-sectionally/sector standardized | Valid | High | `quant/technical_v2.py:240-252` | `fit_ridge_model` computes one training-set mean/std vector. There is no per-date cross-sectional z-score or rank normalization. |
| Quality gates double-count features already in the model | Valid | High | `quant/technical_v2.py:27-49`, `quant/technical_v2.py:180-188`, `quant/technical_v2.py:298-331` | RSI, ADX, volume, trend, weekly trend, and divergence appear in both `FEATURE_NAMES` and post-model gate multipliers. |
| Allocation is rank-driven, not risk-driven | Valid for V2 workflow | High | `quant/allocation.py:90-188` | Allocation uses rank score, hard caps, sector caps, and cash reserve. No covariance, vol target, factor exposure, beta control, or turnover objective. |
| App has no covariance/risk portfolio capability at all | Not literally true | Medium | `quant/portfolio.py:12-113`, `README.md:50-55` | There is a separate `quant optimize` path with inverse-vol, min-variance, and max-Sharpe methods. But it is not integrated into V2 recommendations and is static/full-sample research, so the audit's practical criticism still stands. |
| Execution cost model is optimistic/incomplete | Valid with nuance | Medium-high | `quant/backtest.py:19-20`, `quant/backtest.py:126-138`, `quant/simulator.py:23-25`, `quant/execution.py:10-11` | At USD 20k in mega-caps, market impact can be tiny, so "2 bps is always fantasy" is too broad. But spread, order type, non-fill probability, commissions, adverse selection, and event-day costs are not modeled well enough. |
| Fixed stops may leak expectancy | Partially valid | Medium | `quant/technical_v2.py:334-361`, `quant/recommendations.py` | This is strategy-dependent, not universally true. The valid criticism is that stop/target rules are heuristic and not separately validated across regimes. |
| V1 paper-simulation results are not credible evidence of alpha | Valid | Critical | `quant/simulator.py:13-190` plus current universe usage | Simulator tries to use prior information for signals, but a current-winner universe contaminates historical conclusions. |
| IC of 0.11 cannot be trusted as final evidence | Valid | High | `quant/technical_v2.py:255-295` | The number may be meaningful, but until purge/embargo/CPCV and multiple-testing corrections exist, it is directional evidence only. |
| "All 21 features are price/volume, the most crowded alpha source" | Valid with nuance | High | `quant/technical_v2.py:27-122` | Momentum/trend can still be economically real, but a pure technical model is likely more regime-dependent and more arbitraged than a multi-source model. |
| Today's 20k recommendation is auditable but not production-grade | Valid | High | `INTEGRATED_WORKFLOW_AND_RECOMMENDATION_2026-05-09.md:607-613` | The existing report already admits yfinance, survivorship, daily bars, and allocation-study limitations. |

## What This Means For Earlier Results

The earlier 595 percent style V1 result should be relabeled as a biased demonstration, not evidence of a live edge. The simulator's "veil of ignorance" is only about not using future prices inside a given ticker's signal path. It does not solve the larger problem of selecting today's winners as the past universe.

The V2 recommendation table is more careful than V1, but it still has three major problems:

1. The model trains on a current biased universe.
2. The validation uses overlapping future-return labels without explicit purge/embargo.
3. The portfolio uses model rank and heuristic gates rather than an ex-ante risk model.

So the system can produce useful research hypotheses today, but it should not present current recommendations as production-grade portfolio instructions yet.

## Non-Negotiable Research Principles

1. Every backtest must know the exact universe that existed on each decision date.
2. Every feature must have an `available_at` timestamp. The system must never use data that was published after the decision cutoff.
3. Every label must carry a start and end date. Any train/test split must purge overlapping label windows and embargo after test windows.
4. Every promoted result must include the number of tried variants, not just the winning run.
5. Every recommendation must separate alpha score, risk sizing, execution assumption, and final order plan.
6. Every report must say whether the data is demo-grade, research-grade, or production-grade.
7. No performance claim should be based on synthetic/mock data. Synthetic fixtures are acceptable only for unit tests that prove algorithms work, not for trading conclusions.

## Repair Plan

### Phase 0 - Stop Overstating Current Evidence

Goal: Prevent the app from implying false confidence while we fix the engine.

Tasks:

1. Add a `research_grade_status` block to every V1/V2 JSON output.
2. Mark existing yfinance/current-universe reports as `survivorship_biased_directional_only`.
3. In `INTEGRATED_WORKFLOW_AND_RECOMMENDATION_2026-05-09.md`, add a clear front-matter warning that the recommendation path is not yet production-grade.
4. In CLI output, show data quality badges:
   - `DEMO`: yfinance + current universe.
   - `RESEARCH`: point-in-time universe + vendor historical bars + delistings.
   - `PRODUCTION_CANDIDATE`: research data plus purged CPCV, DSR/PBO, execution model, and risk optimizer.
5. Add a run-manifest schema:
   - git commit or dirty flag
   - command and parameters
   - universe source and version
   - data source and fetch timestamps
   - feature set version
   - validation method
   - cost model version
   - output files and hashes

Files:

- `quant/experiments.py`
- `quant/reporting.py`
- `quant/cli.py`
- `quant/process.py`
- report markdown templates

Done means:

- No CLI command can emit a performance table without an explicit data-quality classification.
- Existing reports cannot be mistaken for production-grade evidence.

### Phase 1 - Data Integrity And Survivorship Bias

Goal: Replace current-winner universe testing with point-in-time membership and delisted history.

Current issue:

- `DEFAULT_RECOMMENDATION_UNIVERSE` is a current hand-picked list.
- `quant/universe.py` has a point-in-time CSV abstraction, but no real vendor-grade security master or delisted-price dataset is installed.
- The Wikipedia S&P 500 adapter explicitly warns that it is not vendor-grade.

Production design:

1. Create a security master table:

```text
security_id
vendor_id
symbol
name
exchange
country
asset_type
sector
industry
first_trade_date
last_trade_date
delisted_flag
delisting_date
delisting_return
corporate_action_adjustment_mode
source
source_version
```

2. Create point-in-time universe membership:

```text
universe_name
security_id
effective_from
effective_to
source
source_version
```

3. Add provider adapters:
   - `NorgateUniverseProvider` for historical constituent membership and delisted names if user obtains Norgate.
   - `CRSPUniverseProvider` for CRSP/WRDS exports if available.
   - `UserCsvUniverseProvider` for manually loaded point-in-time vendor exports.
   - Keep `WikipediaSP500Provider` but label it `demo_research_only`.

4. Add price-history ingestion:
   - adjusted close and raw OHLCV if vendor supplies both
   - splits and dividends
   - delisting returns
   - missing bars and trading halts
   - symbol changes mapped by permanent security ID, not ticker string

5. Universe backtest rules:
   - At rebalance date `t`, select only securities active in universe on `t`.
   - Do not require all securities to survive to the backtest end.
   - Include delisting returns in performance.
   - Allow current names, delisted names, and symbol-renamed names.

Files:

- `quant/universe.py`
- `quant/data.py`
- new `quant/security_master.py`
- new `quant/data_quality.py`
- new `data/universes/README.md`

Tests:

- A ticker that delists midway is eligible before delisting and absent after.
- A ticker rename maps to one security ID across the whole history.
- A backtest over a date range does not silently drop securities that fail before `end`.
- A report refuses to call itself research-grade without delisted coverage.

Done means:

- V1 and V2 can run on a point-in-time universe with delisted members.
- The current default universe is no longer used for historical performance claims.

### Phase 2 - Leakage-Aware Validation

Goal: Make V2 validation defensible.

Current issue:

- `build_training_samples` uses labels from `T` to `T+horizon`.
- `walk_forward_validate_samples` trains on earlier sorted rows and tests on later rows, but does not store label-window end dates and does not purge overlapping labels.
- With `horizon=63` and `step=21`, label overlap is real.

Production design:

1. Change every sample to include:

```text
ticker
feature_date
label_start_date
label_end_date
forward_return
forward_benchmark_return
forward_active_return
feature_vector
```

2. Implement purge:
   - For a test fold with label windows `[test_start, test_end_label]`, remove any training sample whose label interval overlaps any test label interval.

3. Implement embargo:
   - Remove training samples whose feature dates occur within `embargo_days` after the test fold.
   - Start conservatively with `embargo_days = max(10, ceil(horizon * 0.15))`.
   - Also run an embargo sensitivity report at several levels, including a full-horizon embargo for long labels such as 63 trading days.
   - If smaller embargo values materially improve IC, treat that as possible leakage evidence, not as proof that the smaller embargo is safe.

4. Implement validation methods:
   - Purged walk-forward.
   - Purged K-fold by date groups.
   - CPCV: split dates into `N` ordered groups, choose `k` groups as test, purge/embargo, aggregate path-level results.

5. Report:
   - mean/median IC
   - IC standard deviation
   - IC t-stat and bootstrap CI
   - quantile spread returns
   - top minus bottom quintile
   - long-short diagnostic Sharpe
   - PBO estimate
   - Deflated Sharpe Ratio
   - number of trials included in DSR

Files:

- new `quant/validation_purged.py`
- new `quant/model_selection.py`
- new `quant/backtest_diagnostics.py`
- `quant/technical_v2.py`
- `quant/reporting.py`

Tests:

- Deliberately overlapping labels are removed from training.
- Embargo removes post-test observations.
- CPCV returns multiple paths, not one path.
- PBO and DSR functions handle small and degenerate samples safely.

Done means:

- The app no longer reports V2 IC as a single optimistic walk-forward average.
- Reports include a distribution of results and explicit overfit risk.

### Phase 3 - Cross-Sectional Feature Treatment

Goal: Stop treating raw technical values as comparable across all securities and regimes.

Current issue:

- A 5 percent 21-day move in KO and a 5 percent 21-day move in NVDA are not equivalent.
- The model uses training-set standardization, not per-date cross-sectional normalization.

Production design:

1. Build a date-symbol feature panel:

```text
index: feature_date, ticker/security_id
columns: raw_features, sector, industry, liquidity, benchmark_beta
```

2. Add transformations:
   - winsorize within date
   - z-score within date across universe
   - rank-transform within date
   - sector-neutral z-score
   - industry-neutral z-score where available
   - volatility-scaled momentum
   - residual momentum after sector ETF return

3. Keep raw and transformed features separate:
   - `mom_63_raw`
   - `mom_63_xsec_z`
   - `mom_63_sector_z`
   - `mom_63_residual_sector`

4. Choose model input using validation, not intuition.

Files:

- new `quant/features.py`
- new `quant/feature_store.py`
- new `quant/factors.py`
- `quant/technical_v2.py`

Tests:

- Per-date z-scores have near-zero mean and unit variance.
- Sector-neutral transformations do not leak future sector membership.
- Transformations use only same-date cross-section, not future returns.

Done means:

- The model can compare securities on a normalized cross-sectional basis.
- Reports can show whether raw, z-scored, rank, or sector-neutral signals performed best under purged validation.

### Phase 4 - Model/Gate Decoupling

Goal: Remove hidden degrees of freedom and feature double-counting.

Current issue:

- `rank_score = predicted_63d_active_return * quality_multiplier`.
- The quality multiplier uses RSI, ADX, trend, volume, and divergence, which are already model features.

Clean options:

Option A - Pure model:

- Keep technical features inside ridge.
- Remove alpha-style multipliers.
- Use gates only as hard risk exclusions for non-alpha facts, such as:
  - bad data quality
  - insufficient liquidity
  - earnings within blocked window, if configured
  - borrow unavailable for short book
  - extreme realized volatility
  - failed trend regime only if it is not a model feature

Option B - Pure overlay:

- Remove RSI/ADX/divergence/volume/trend features from the model.
- Keep them as a separate discretionary/risk overlay.
- Validate overlay thresholds as hyperparameters inside nested purged validation.

Recommended path:

- Use Option A for V2. The model is supposed to learn the signal. Do not multiply calibrated returns by unvalidated gates.
- Rename the current gate multiplier to `legacy_quality_overlay`.
- Add a report field showing both `model_prediction` and `legacy_overlay_rank`.
- Run both ranking paths in parallel for at least three months of paper/live-shadow logging before retiring the overlay.
- Promote the pure-model path only if post-cost live/paper IC, calibration, and drawdown behavior are at least as good as the legacy overlay. If the overlay wins, treat that as a research clue and re-model the effect instead of silently keeping a hidden multiplier.

Additional model upgrades:

1. Predict cross-sectional rank or z-scored forward active return alongside raw active return.
2. Add horizon testing: 5d, 21d, 42d, 63d, 126d.
3. Add IC decay chart.
4. Add calibration bins: predicted return decile vs realized active return.
5. Add coefficient stability across folds.
6. Add nested validation for ridge alpha and feature-set selection.

Files:

- `quant/technical_v2.py`
- new `quant/models.py`
- new `quant/model_reports.py`

Tests:

- No model input column can also appear in production gate logic unless explicitly marked `risk_only`.
- Changing RSI threshold cannot silently change production rank unless that threshold was part of validated hyperparameters.
- Prediction units remain clear: raw expected return vs rank score vs portfolio weight.

Done means:

- The ranking is attributable to the model, and risk filters are attributable to risk policy.

### Phase 5 - Factor Diagnostics And Long-Short Skill Measurement

Goal: Know whether the model picks stocks or just rides market/sector beta.

Current issue:

- Current reports emphasize top recommendations and long-only allocations.
- There is no full Alphalens-style factor tear sheet.

Production design:

1. Build factor data from V2 predictions:
   - date
   - asset
   - factor value
   - forward returns at 1d, 5d, 21d, 63d, 126d
   - group/sector

2. Compute:
   - Spearman IC by date and horizon
   - mean IC by month/quarter/year
   - IC decay
   - top/bottom quantile spread
   - mean return by quantile
   - quantile turnover
   - factor rank autocorrelation
   - beta/sector exposures by quantile
   - long-short top-minus-bottom diagnostic
   - group-neutral long-short diagnostic

3. Promote a model only if:
   - IC is positive after purge/embargo
   - quantile returns are monotonic or plausibly monotonic
   - long-short spread survives transaction costs
   - top-quintile performance is not entirely one sector/regime
   - live/paper IC does not decay materially

Files:

- new `quant/factor_diagnostics.py`
- new `quant/plots.py`
- `quant/reporting.py`

Tests:

- Factor IC uses same-date cross-section and future returns only for scoring.
- Group-adjusted IC demeans returns by group.
- Turnover metrics are stable under ticker order changes.

Done means:

- The report can answer: "Does the signal have stock-selection skill independent of beta?"

### Phase 6 - Risk-Aware Portfolio Construction

Goal: Convert alpha forecasts into weights using risk, correlation, constraints, and turnover.

Current issue:

- V2 allocation in `quant/allocation.py` sorts by `rank_score` and applies caps.
- Separate `quant/portfolio.py` has basic static covariance methods, but not integrated into V2 and not walk-forward.

Production design:

1. Build a `PortfolioOptimizer` input:

```text
candidate universe
expected_active_returns
current_weights
rolling_returns_panel
sector/industry map
benchmark weights or beta estimates
cash target
commission/slippage/impact estimates
constraints
```

2. Compute risk model:
   - 60d, 126d, and 252d covariance options
   - exponentially weighted covariance
   - Ledoit-Wolf/shrinkage covariance if dependency is available
   - beta to SPY/QQQ
   - sector ETF betas
   - realized vol and liquidity

3. Implement allocation methods:
   - inverse-vol/risk-parity baseline
   - minimum variance
   - max quadratic utility: `w dot mu - lambda * w.T Sigma w`
   - tracking-error constrained active portfolio
   - HRP if using PyPortfolioOpt/Riskfolio-Lib
   - optional blend of robust risk parity and expected-return optimizer, with the blend weight selected by purged validation rather than fixed at a round number
   - every tried blend weight must be logged as a tried variant for later DSR/PBO correction

4. Constraints:
   - long-only for the default app
   - max position
   - min position
   - max sector and industry
   - max ETF overlap
   - max predicted portfolio vol
   - max beta to SPY and QQQ
   - max turnover
   - cash floor
   - no trade if expected edge after costs is below threshold

5. Turnover and costs:
   - penalize `abs(w_new - w_old)` and/or squared turnover
   - subtract expected commission/spread/slippage from expected return
   - keep weights sticky when signals are close

Files:

- new `quant/portfolio_optimizer.py`
- `quant/allocation.py`
- `quant/portfolio.py`
- `quant/cli.py`

Tests:

- Weights sum to target gross exposure.
- Constraints are actually enforced.
- Higher covariance between two names reduces combined concentration.
- Higher expected trading cost reduces target weight.
- Current-weight input reduces unnecessary turnover.

Done means:

- A recommendation is not just "top rank"; it is "top rank after expected return, risk, correlation, and cost."

### Phase 7 - Execution Model And Implementation Shortfall

Goal: Estimate how much paper alpha survives real orders.

Current issue:

- Costs are simple basis-point assumptions.
- Limit entries are recommended, but the simulator does not model whether they fill.
- Commission settings exist but are not connected to broker-specific order economics.

Production design:

1. Add `ExecutionModel`:
   - broker commission schedule
   - spread estimate
   - slippage estimate by volatility/liquidity/regime
   - market-impact estimate
   - participation cap
   - limit-order fill probability
   - partial-fill logic
   - no-fill opportunity cost

2. Slippage/cost inputs:
   - baseline spread from OHLC proxy when true bid/ask unavailable
   - higher slippage in high-vol regimes
   - higher slippage near earnings/FOMC/CPI if event calendar available
   - minimum ticket commission, e.g. IBKR small commission around USD 1 where applicable

3. Implementation shortfall report:
   - decision price
   - intended order price
   - simulated fill price
   - missed fills
   - explicit fees
   - spread/slippage cost
   - delay cost
   - opportunity cost
   - alpha before cost vs after cost

Files:

- `quant/execution.py`
- new `quant/execution_model.py`
- `quant/simulator.py`
- `quant/backtest.py`
- `quant/reporting.py`

Tests:

- Buy orders pay ask-like slippage and sell orders pay bid-like slippage.
- No-fill scenarios are represented in P&L.
- A higher commission schedule changes optimizer decisions.
- Partial fills respect volume participation.

Done means:

- Every paper/live recommendation has expected implementation shortfall, not just theoretical entry/stop/target.

### Phase 8 - Orthogonal Data Sources

Goal: Stop relying only on price/volume.

Current issue:

- All V2 model features are technical.

Production design:

1. Fundamentals:
   - point-in-time revenue growth
   - gross margin and operating margin trend
   - ROIC/ROE
   - leverage
   - valuation metrics
   - earnings revision breadth if source available

2. Sentiment:
   - historical news provider with immutable `published_at`
   - article-level sentiment scored only from text available at that time
   - no LLM use of memorized future knowledge in historical simulations
   - for historical backtests, prefer timestamp-safe lexicon/statistical methods such as Loughran-McDonald-style financial sentiment dictionaries unless the sentiment model's training cutoff is safely before the article date
   - use LLM sentiment mainly for live/forward analysis or for historical text extraction where the output can be constrained to source-local facts, not future-aware judgment

3. Flow/positioning:
   - short interest
   - options put/call ratio or skew
   - ETF flow if source available

4. Macro/regime:
   - VIX level and change
   - Treasury yield changes
   - credit spread proxy
   - SPY trend/regime
   - market breadth

Feature rules:

- Every non-price feature needs:
  - `as_of_date`
  - `published_at`
  - `effective_date`
  - source
  - revision/version
  - missing-data policy

Files:

- new `quant/altdata/`
- new `quant/fundamentals.py`
- new `quant/sentiment.py`
- new `quant/macro.py`
- `quant/features.py`

Tests:

- A feature published after a simulated decision date is unavailable.
- Restated fundamentals do not overwrite what was known historically without versioning.
- Missing features are imputed using training-period rules only.

Done means:

- V2 becomes a multi-source alpha model rather than a pure technical model.

### Phase 9 - Regime Conditioning

Goal: Stop averaging trend, chop, crisis, and liquidity regimes into one coefficient vector.

Current issue:

- One ridge model is trained across all regimes.

Production design:

1. Start simple:
   - add VIX/SPY trend/breadth/realized-vol regime features.
   - let ridge learn conditional effects.

2. Add explicit regimes:
   - bull trend
   - bear trend
   - high-vol crisis
   - low-vol chop
   - liquidity stress

3. Later:
   - separate model per regime
   - ensemble/meta-model to blend regime models
   - dynamic vol target by regime

Files:

- new `quant/regime.py`
- `quant/technical_v2.py`
- `quant/models.py`
- `quant/portfolio_optimizer.py`

Tests:

- Regime labels use only data available by decision date.
- Regime model fallback works when a regime has too little training data.

Done means:

- The engine can say not just "this is a good stock", but "this signal has historically worked in this market regime."

### Phase 10 - Live/Paper Monitoring

Goal: Detect signal decay and live execution drift.

Current issue:

- Runs are saved under `runs/`, but there is no continuous live/paper IC and implementation-shortfall dashboard.

Production design:

1. Log every recommendation:
   - run ID
   - decision time
   - universe
   - features
   - raw prediction
   - risk filters
   - target weight
   - order plan

2. Later attach realized outcomes:
   - 1d/5d/21d/63d returns
   - active returns
   - fill results
   - fees/slippage
   - stop/target hit path

3. Monitor:
   - rolling IC
   - IC decay
   - top/bottom quantile spread
   - realized vs predicted calibration
   - turnover
   - factor exposures
   - drawdown
   - implementation shortfall

4. Alert thresholds:
   - live 60-day IC below 50 percent of validated IC
   - live IC negative over a full horizon
   - realized slippage above model by 2x
   - factor exposure breach
   - drawdown breach

Files:

- new `quant/monitoring.py`
- `quant/experiments.py`
- `quant/critic.py`
- `quant/reporting.py`

Tests:

- Realized labels are attached only after horizon completion.
- Monitoring cannot use incomplete future labels as if they were final.

Done means:

- The app can tell when the model is degrading instead of silently continuing.

### Phase 11 - IBKR/Broker Integration, Later And Gated

Goal: Make live execution possible only after research controls pass.

Current issue:

- There is an IBKR plan document, and Alpaca paper support exists, but the validated strategy is not yet ready for direct live trading.

Safe rollout:

1. Manual-only mode:
   - Generate recommendations.
   - User manually places trades.
   - App records intended vs actual fills.

2. Paper broker mode:
   - IBKR paper or Alpaca paper.
   - Same order planner as live.
   - No real capital.

3. Shadow live mode:
   - App generates orders but does not submit.
   - Compare simulated order plan to market outcomes.

4. Small live sleeve:
   - fixed max capital
   - max daily loss
   - max order size
   - kill switch
   - manual approval for every order
   - no shorting initially
   - no orders around earnings/events unless explicitly enabled

5. Fully automated mode:
   - only after months of paper/live-shadow monitoring
   - only if live IC and implementation shortfall match research expectations

Done means:

- Broker integration cannot outrun validation.

## Implementation Order

This is the order I would actually execute.

1. Phase 0: add honesty/status flags to stop overstating results.
2. Phase 1: point-in-time universe and delisted/security-master data.
3. Phase 2: purged validation, embargo, CPCV, PBO, DSR.
4. Phase 3: cross-sectional feature panel and sector-neutral transformations.
5. Phase 4: remove gate double-counting.
6. Phase 5: factor diagnostics and long-short skill measurement.
7. Phase 6: risk-aware portfolio optimizer integrated into V2.
8. Phase 7: execution model and implementation shortfall.
9. Phase 10: monitoring, because paper/live decay must be visible once recommendations are made.
10. Phase 8: fundamentals/sentiment/flow/macro data.
11. Phase 9: regime conditioning.
12. Phase 11: IBKR integration.

Reasoning:

- Data and validation come first because without them every later improvement can be optimized against contaminated evidence.
- Cross-sectional treatment and gate decoupling are high-impact and relatively contained.
- Portfolio construction should wait until `mu` is more trustworthy, but the scaffolding can start once validation exists.
- Alternative data is powerful, but not before the point-in-time and leakage machinery exists.

## Concrete Milestones

### Milestone A - Honest Research Baseline

Deliverables:

- Data-quality badge in outputs.
- Existing reports relabeled.
- Run manifest.
- No production-grade language for yfinance/current-universe results.

Acceptance:

- User can open any report and immediately know whether it is demo-grade or research-grade.

### Milestone B - Unbiased Universe

Deliverables:

- Vendor/user-export universe provider.
- Security master.
- Delisting support.
- Re-run V1/V2 with corrected universe.

Acceptance:

- Backtests include names that existed then, not just names that survived until now.

### Milestone C - Defensible V2 Validation

Deliverables:

- Purged/embargoed samples.
- CPCV.
- PBO and DSR.
- IC distribution.
- Quantile spread and long-short diagnostics.

Acceptance:

- A skeptical quant can inspect train/test splits and not find label leakage.

### Milestone D - Cleaner Alpha Engine

Deliverables:

- Cross-sectional/sector-neutral feature panel.
- Gate/model decoupling.
- Horizon/IC decay analysis.
- Coefficient stability report.

Acceptance:

- Ranking has clear attribution and no hidden double-counted multiplier.

### Milestone E - Risk-Driven Portfolio

Deliverables:

- V2 optimizer using expected return, covariance, costs, and constraints.
- Vol targeting.
- Factor/sector/beta exposure report.
- Turnover-aware allocations.

Acceptance:

- Two highly correlated tech names cannot both receive large weights just because they rank well.

### Milestone F - Execution Reality

Deliverables:

- Fill-probability model.
- Broker cost schedule.
- Implementation shortfall report.
- Paper execution tracker.

Acceptance:

- Report shows expected alpha before and after execution costs and missed fills.

### Milestone G - Monitoring And Broker Readiness

Deliverables:

- Live/paper IC dashboard.
- Slippage/shortfall dashboard.
- Kill-switch policy.
- Manual-approval IBKR order planner.

Acceptance:

- The app can prove it is behaving out of sample before any direct live automation.

## Final Assessment

I would rate the current system as:

- Research prototype: 6/10.
- Honest documentation/transparency: 8/10.
- Production readiness for real money: 3.5 to 4/10.
- Potential after Phases 0-7 are completed and validated under stress: 6.5 to 7.5/10.
- Potential above 8/10 requires Phases 8-10 plus several quarters of out-of-sample evidence that does not degrade.

The external audit is not being unfair about the big issues. The five headline problems are valid. The only meaningful corrections are:

1. The app has a separate basic covariance optimizer, but the V2 recommendation workflow does not use it.
2. The execution-cost criticism is directionally valid, but "2 bps is always impossible" is too broad at USD 20k in mega-cap names.
3. The fixed-stop criticism is plausible but must be validated empirically; it is not a universal law.

The most honest path forward is to demote current outputs to "hypothesis generation", build the data/validation foundation, and only then rerun the model to see what edge survives.
