# Integrated Quant Lab Workflow And Recommendation

Date prepared: 2026-05-09  
Latest market data used by the app: daily adjusted OHLCV through 2026-05-08  
Capital sleeve analyzed: USD 20,000  
This is a research and paper-trading report, not financial advice.

Research-grade status: **DEMO**. This report uses yfinance/Yahoo daily bars and a current/default liquid universe. It is useful for hypothesis generation and app inspection, but it is not survivorship-bias-free production evidence.

## Executive Summary

Quant Lab currently has two technical engines:

1. **V1 deterministic engine**: simple, rule-based strategies used for backtests, decision audits, and historical paper simulations.
2. **V2 calibrated technical engine**: transparent feature extraction plus a ridge-regression model calibrated on historical forward active returns versus `SPY`.

V2 does **not** run after V1. They are separate engines. V1 remains useful as a baseline and simulator. V2 is now the preferred recommendation engine because it uses calibrated feature weights instead of hand-weighted scores.

For today, the app ran:

- V2 calibrated recommendation scan across the default liquid universe.
- V2 allocation policy for a USD 20,000 sleeve.
- V1 historical paper simulation on a focused recommendation universe for context.

Final app-generated allocation:

| Ticker | Sector Bucket | Allocation | Entry Style | Entry | Stop | Target |
|---|---:|---:|---|---:|---:|---:|
| `TXN` | semiconductor | $3,166.76 | pullback | $259.16 | $239.29 | $298.90 |
| `CAT` | industrial | $3,142.47 | pullback | $843.46 | $782.18 | $966.00 |
| `AMAT` | semiconductor | $2,400.00 | pullback | $404.93 | $368.77 | $488.08 |
| `GOOGL` | mega_tech | $2,175.93 | pullback | $359.73 | $339.01 | $401.17 |
| `XLK` | sector_etf | $2,054.51 | pullback | $159.58 | $152.93 | $172.87 |
| `AAPL` | mega_tech | $1,400.00 | pullback | $274.84 | $261.11 | $302.29 |
| `QQQ` | broad_etf | $1,432.81 | pullback | $663.33 | $646.70 | $693.26 |
| `CSCO` | networking | $1,340.53 | pullback | $89.49 | $84.40 | $99.67 |
| Cash | reserve | $2,886.99 | n/a | n/a | n/a | n/a |

The allocation is deliberately pullback-oriented because many high-ranked names are extended or have bearish RSI divergence. The app did not recommend chasing the most explosive names at current prices.

## What The App Actually Does Today

The current codebase does the following:

- Fetches historical daily OHLCV data from `yfinance`.
- Caches some data paths in SQLite.
- Runs deterministic V1 strategy backtests and paper simulations.
- Runs V2 calibrated technical recommendations.
- Builds entry-specific pullback and breakout trade plans.
- Applies a USD 20,000 allocation policy with sector caps, trend gates, cash reserve, and risk exclusions.
- Models zero default broker commission, 2 bps slippage, cash, fills, rejected orders, and volume participation caps in historical paper simulation.
- Produces explainable reports and JSON outputs.

The app does **not** currently do the following:

- It does not ingest fundamentals.
- It does not ingest earnings calendars.
- It does not ingest current news in this recommendation path.
- It does not model Hong Kong tax treatment.
- It does not model IBKR-specific live order behavior yet.
- It does not use real-time order book or intraday data for this report.
- It does not use options flow or short interest.
- It does not provide legal, tax, or financial advice.

## Data Workflow

The recommendation workflow starts with daily OHLCV bars:

```text
yfinance daily OHLCV
-> normalized internal bar format
-> feature frame
-> V1 simulation or V2 calibrated recommendation
-> allocation policy
-> markdown report
```

The latest available data in this run was 2026-05-08. Because today is 2026-05-09 in Hong Kong, this means the report uses the latest completed U.S. market session available to the app.

## Universe Selection

For V2, the app used its default liquid recommendation universe from `quant/technical_v2.py`. It includes:

- Broad ETFs: `SPY`, `QQQ`, `IWM`, `VOO`, `VTI`
- Sector ETFs: `XLK`, `XLF`, `XLE`, `XLV`, `XLI`, `SMH`, `SOXX`
- Large liquid equities across technology, semiconductors, financials, healthcare, energy, consumer, industrials, software, and growth.

This universe is practical for research, but it is not a survivorship-bias-free institutional universe. It is a current liquid watchlist.

## V1 Engine

V1 is deterministic and rule-based. It lives mainly in:

- `quant/strategies.py`
- `quant/backtest.py`
- `quant/simulator.py`
- `quant/execution.py`

V1 supports:

| Strategy | Rule |
|---|---|
| `momentum` | Buy/hold if trailing 63-trading-day return is positive. Rank by 63-day momentum. |
| `sma_cross` | Buy/hold if 20-day SMA is above 50-day SMA. Rank by `20-day SMA / 50-day SMA - 1`. |
| `buy_hold` | Always eligible. |

V1 simulation behavior:

1. Aligns all symbols by common trading dates.
2. Uses a warmup window before the first decision.
3. At rebalance date `T`, uses `closes[:T]`, excluding the current and future close.
4. Selects the top `max_positions` qualifying names.
5. Equal-weights selected names.
6. Sends target orders through `BrokerSimulator`.
7. Applies slippage, cash checks, volume participation caps, fills, and rejected orders.
8. Marks holdings to market daily.

V1 is useful because it is simple and auditable. It is not rich enough to produce the final recommendation by itself.

## V1 Historical Paper Simulation

The app ran a V1 historical paper simulation for context:

```text
Universe: SPY, QQQ, NVDA, AVGO, AMAT, MS, WMT, COST, IWM
Strategy: momentum
Capital: $20,000
Start requested: 2018-01-01
Actual first trade after warmup: 2019-01-03
End: 2026-05-08
Max positions: 5
Commission: 0 bps
Slippage: 2 bps
Max volume participation: 2.5%
```

Simulation summary:

| Metric | Value |
|---|---:|
| Initial capital | $20,000.00 |
| Final equity | $137,510.96 |
| PnL | $117,510.96 |
| SPY benchmark final equity | $67,342.03 |
| SPY benchmark PnL | $47,342.03 |
| Rebalances | 88 |
| Average turnover | 0.6264 |
| Fees | $0.00 |
| Slippage | $656.92 |
| Fills | 473 |
| Rejected/partial orders | 93 |
| Total return | 595.18% |
| Annual return | 30.30% |
| Annual volatility | 27.53% |
| Sharpe | 1.0993 |
| Sortino | 1.4340 |
| Max drawdown | -45.97% |
| Alpha | 10.10% |
| Beta | 1.1209 |
| Information ratio | 0.6981 |

Last five V1 rebalance targets:

| Date | Target Weights |
|---|---|
| 2025-12-09 | `NVDA`, `AVGO`, `AMAT`, `MS`, `WMT` at 20% each |
| 2026-01-09 | `SPY`, `AMAT`, `MS`, `WMT`, `IWM` at 20% each |
| 2026-02-10 | `AMAT`, `MS`, `WMT`, `COST`, `IWM` at 20% each |
| 2026-03-12 | `NVDA`, `AMAT`, `WMT`, `COST`, `IWM` at 20% each |
| 2026-04-13 | `NVDA`, `AVGO`, `AMAT`, `WMT`, `COST` at 20% each |

Interpretation:

- V1 momentum performed strongly in this universe.
- That result should not be treated as proof of future performance.
- The universe is current-watchlist biased and contains major winners.
- V1 is useful as a sanity-check simulator, not the final ranking method.

## V2 Engine

V2 is the recommendation engine used for today’s portfolio. It lives mainly in:

- `quant/technical_v2.py`
- `quant/recommendations.py`
- `quant/allocation.py`

V2 does not assign arbitrary `+25` or `+20` points. Instead, it:

1. Computes a transparent technical feature table.
2. Builds historical samples.
3. Fits a standardized ridge-regression model.
4. Predicts forward active return versus `SPY`.
5. Applies explicit quality gates.
6. Builds entry-specific pullback and breakout plans.
7. Passes recommendations to the allocation policy.

## V2 Feature Table

V2 computes:

| Feature | Meaning |
|---|---|
| `mom_21` | 21-trading-day return |
| `mom_63` | 63-trading-day return |
| `mom_126` | 126-trading-day return |
| `price_vs_sma200` | close / 200-day SMA - 1 |
| `sma20_vs_sma50` | 20-day SMA / 50-day SMA - 1 |
| `sma50_vs_sma200` | 50-day SMA / 200-day SMA - 1 |
| `sma50_slope_20` | 20-day rate of change in 50-day SMA |
| `sma200_slope_40` | 40-day rate of change in 200-day SMA |
| `adx_14` | ADX divided by 100 |
| `di_spread` | +DI minus -DI divided by 100 |
| `rsi_14` | 14-day RSI |
| `rsi_extension` | distance from healthy trend RSI |
| `rel_volume_20` | current volume / 20-day average volume |
| `breakout_pressure` | close / prior 20-day high - 1 |
| `atr_pct` | 14-day ATR / close |
| `weekly_price_vs_sma40` | weekly close / weekly 40-SMA - 1 |
| `weekly_sma10_vs_sma40` | weekly 10-SMA / weekly 40-SMA - 1 |
| `weekly_sma40_slope` | 8-week rate of change in weekly 40-SMA |
| `price_position_20` | close location inside 20-day high/low range |
| `bearish_rsi_divergence` | price high without RSI high |
| `bullish_rsi_divergence` | price low without RSI low |

## V2 Calibration Target

The target is:

```text
63-day forward active return =
  ticker 63-day forward return
- SPY 63-day forward return
```

Each training row uses features known at date `T`. The target uses future returns from `T` to `T + 63`. For today’s recommendations, no future target exists; the model only uses the fitted relationship and latest known features.

## V2 Model

Model type:

```text
standardized ridge regression
```

Standardization:

```text
z = (feature - training_mean) / training_std
```

Prediction:

```text
predicted_active_return = intercept + z @ coefficients
```

The ridge penalty is used because technical features are correlated. For example, 63-day momentum, 126-day momentum, moving-average slope, and price above moving averages all overlap. Ridge regression reduces coefficient instability.

## V2 Walk-Forward Validation

The app ran walk-forward validation over the V2 sample set.

| Validation Item | Value |
|---|---:|
| Calibration samples | 5,502 |
| Symbols scanned | 65 |
| Walk-forward folds | 65 |
| Average rank correlation | 0.1139 |
| Average top-quintile active return | 4.83% |
| Average all-sample active return | 1.73% |
| Average top-quintile hit rate | 54.23% |

Interpretation:

- The model has a positive but modest ranking signal.
- It is not a magic predictor.
- The top quintile historically beat the average sample in this run.
- A 54.23% hit rate is useful only with risk control; it is not high enough to justify oversized bets.

## V2 Quality Gates

The app uses explicit gates after prediction:

| Gate | Meaning |
|---|---|
| Daily trend | close > 200-day SMA, 20-day SMA > 50-day SMA, and 50-day SMA slope positive |
| Weekly trend | weekly close > weekly 40-SMA, weekly 10-SMA > weekly 40-SMA, weekly 40-SMA slope positive |
| ADX strength | classifies trend as weak, moderate, or strong |
| Volume breakout | relative volume >= 1.2 and breakout pressure > 0 |
| Overbought RSI | penalizes very hot names |
| Bearish RSI divergence | penalizes price highs not confirmed by RSI |
| Bullish RSI divergence | exposed for audit |

The model output is not accepted blindly. The final ranking is:

```text
rank_score = predicted_63d_active_return * quality_multiplier
```

## Current V2 Top-Ranked Names

The raw V2 top list included several extremely strong semiconductor names. The table below shows the current top names before allocation exclusions.

| Ticker | Price | Predicted 63D Active Return | Rank Score | Key Gates |
|---|---:|---:|---:|---|
| `INTC` | $125.99 | 28.39% | 17.04% | overbought, bearish RSI divergence |
| `MU` | $737.36 | 22.60% | 13.56% | overbought, bearish RSI divergence |
| `AMD` | $447.33 | 15.25% | 9.15% | overbought, bearish RSI divergence |
| `TXN` | $288.73 | 8.15% | 6.52% | overbought, no bearish divergence |
| `CAT` | $901.40 | 6.47% | 6.47% | clean gates |
| `AMAT` | $436.13 | 8.46% | 6.34% | bearish divergence but not overbought |
| `SOXX` | $517.84 | 7.65% | 4.59% | overbought, bearish RSI divergence |
| `GOOGL` | $397.77 | 5.59% | 4.48% | overbought, no bearish divergence |
| `SMH` | $564.81 | 7.14% | 4.28% | overbought, bearish RSI divergence |
| `XLK` | $174.95 | 5.29% | 4.23% | overbought, no bearish divergence |
| `QCOM` | $219.25 | 10.74% | 3.87% | weekly trend failed, overbought, bearish divergence |
| `AMZN` | $272.39 | 3.74% | 3.74% | clean gates |

Important: the allocation layer does not automatically buy the highest raw predictions. It excludes names where the risk gates say the setup is too extended or internally weak.

## Allocation Policy

The app used `quant/allocation.py` to convert recommendations into a USD 20,000 research portfolio.

Policy:

| Rule | Value |
|---|---:|
| Capital | $20,000 |
| Target deployable capital | $18,000 |
| Base cash reserve | 10% |
| Maximum positions | 8 |
| Maximum position size | 18% of capital |
| Minimum allocation | $500 |

Exclusion rules:

- Exclude failed daily trend gate.
- Exclude failed weekly trend gate.
- Exclude overbought RSI plus bearish RSI divergence.
- Exclude non-positive rank score.

Sector caps:

| Sector Bucket | Max % of Capital |
|---|---:|
| Broad ETF | 35% |
| Sector ETF | 25% |
| Semiconductor | 30% |
| Mega tech | 25% |
| Software | 20% |
| Networking | 15% |
| Financial | 20% |
| Payments | 15% |
| Energy | 15% |
| Healthcare | 20% |
| Consumer | 25% |
| Industrial | 20% |
| Growth | 15% |
| Crypto beta | 5% |

## Today’s USD 20,000 Portfolio

| Ticker | Allocation | % of Capital | Entry Style | Entry | Stop | Target | Shares At Entry | Est. Dollar Risk |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| `TXN` | $3,166.76 | 15.83% | pullback | $259.16 | $239.29 | $298.90 | 12.2193 | $242.80 |
| `CAT` | $3,142.47 | 15.71% | pullback | $843.46 | $782.18 | $966.00 | 3.7257 | $228.31 |
| `AMAT` | $2,400.00 | 12.00% | pullback | $404.93 | $368.77 | $488.08 | 5.9270 | $214.32 |
| `GOOGL` | $2,175.93 | 10.88% | pullback | $359.73 | $339.01 | $401.17 | 6.0488 | $125.33 |
| `XLK` | $2,054.51 | 10.27% | pullback | $159.58 | $152.93 | $172.87 | 12.8745 | $85.62 |
| `AAPL` | $1,400.00 | 7.00% | pullback | $274.84 | $261.11 | $302.29 | 5.0939 | $69.94 |
| `QQQ` | $1,432.81 | 7.16% | pullback | $663.33 | $646.70 | $693.26 | 2.1600 | $35.92 |
| `CSCO` | $1,340.53 | 6.70% | pullback | $89.49 | $84.40 | $99.67 | 14.9796 | $76.25 |
| Cash | $2,886.99 | 14.43% | reserve | n/a | n/a | n/a | n/a | n/a |

Total allocated to positions: $17,113.01  
Cash reserve: $2,886.99

The cash reserve is larger than the base 10% reserve because the allocation layer rejected several high-ranked names and did not force capital into weaker or overextended setups.

## Why Capital Was Allocated This Way

### TXN

Allocation: $3,166.76  
Reason:

- Predicted 63-day active return: 8.15%.
- Rank score: 6.52%.
- Weekly trend confirmed.
- ADX trend strength: strong.
- Semiconductor exposure was allowed, but sector cap prevented over-concentration.
- Entry style is pullback because current conditions are extended.

### CAT

Allocation: $3,142.47  
Reason:

- Predicted 63-day active return: 6.47%.
- Rank score: 6.47%.
- Weekly trend confirmed.
- ADX trend strength: strong.
- Clean gate profile: not overbought with bearish divergence.
- Provides non-tech industrial exposure.

### AMAT

Allocation: $2,400.00  
Reason:

- Predicted 63-day active return: 8.46%.
- Rank score: 6.34%.
- Weekly trend confirmed.
- ADX trend strength: moderate.
- Bearish divergence exists, but RSI is not flagged as overbought by the allocation rule.
- Position is capped by semiconductor sector risk.

### GOOGL

Allocation: $2,175.93  
Reason:

- Predicted 63-day active return: 5.59%.
- Rank score: 4.48%.
- Weekly trend confirmed.
- ADX trend strength: strong.
- Overbought, but no bearish RSI divergence flag.
- Adds mega-cap tech exposure outside the semiconductor cap.

### XLK

Allocation: $2,054.51  
Reason:

- Predicted 63-day active return: 5.29%.
- Rank score: 4.23%.
- Weekly trend confirmed.
- ADX trend strength: strong.
- Sector ETF exposure provides diversification across technology rather than only single-name concentration.

### AAPL

Allocation: $1,400.00  
Reason:

- Predicted 63-day active return: 3.31%.
- Rank score: 3.31%.
- Weekly trend confirmed.
- ADX trend strength: moderate.
- Position size is smaller because predicted active return is lower and mega-tech exposure is capped.

### QQQ

Allocation: $1,432.81  
Reason:

- Predicted 63-day active return: 3.69%.
- Rank score: 2.95%.
- Weekly trend confirmed.
- ADX trend strength: strong.
- Broad ETF exposure reduces single-name risk.

### CSCO

Allocation: $1,340.53  
Reason:

- Predicted 63-day active return: 3.68%.
- Rank score: 2.76%.
- Weekly trend confirmed.
- ADX trend strength: strong.
- Networking bucket diversifies away from semiconductors and mega-cap tech.

## Why Some High-Ranked Names Were Rejected

| Ticker | Reason |
|---|---|
| `INTC` | overbought with bearish RSI divergence |
| `MU` | overbought with bearish RSI divergence |
| `AMD` | overbought with bearish RSI divergence |
| `SOXX` | overbought with bearish RSI divergence |
| `SMH` | overbought with bearish RSI divergence |
| `QCOM` | weekly trend gate failed; overbought with bearish RSI divergence |
| `NVDA` | semiconductor sector cap reached |
| `AMZN` | mega-tech sector cap reached |
| `PANW` | weekly trend gate failed |
| `XOM` | daily trend gate failed |
| `JNJ` | daily trend gate failed |
| `AVGO` | max position count reached |
| `WMT` | max position count reached |
| `IWM` | max position count reached |

This is the main difference between a raw screener and a portfolio process. The raw model liked several extremely strong semiconductor names, but the allocation layer refused to concentrate the whole $20,000 sleeve into an overextended semiconductor cluster.

## Entry Plan Interpretation

Every selected name uses a pullback entry today.

That does **not** mean the app is saying these stocks are bad. It means current prices are extended relative to the model’s preferred entry logic. A pullback entry is:

```text
min(current close, 20-day SMA + 0.25 * ATR)
```

The stop and target are calculated from that specific entry. This avoids the earlier SPY-style bug where a stop from one entry context was shown beside a different entry.

For each long entry:

```text
support_stop = 50-day SMA - 0.25 * ATR
volatility_stop = entry - regime_ATR_multiple * ATR
stop = max(support_stop, volatility_stop)
```

If the stop would be above the entry, the app forces the stop below entry:

```text
stop = entry - regime_ATR_multiple * ATR
```

## Non-Technical Factors The App Currently Handles

The app currently handles these non-price concerns:

- Capital sleeve size.
- Cash reserve.
- Max number of positions.
- Max single-position size.
- Sector concentration caps.
- Zero default broker commission.
- Slippage assumption.
- Volume participation cap in historical simulation.
- Rejected/partial orders in simulation.
- Data provenance warning.

## Non-Technical Factors The App Does Not Yet Handle

The app does not currently handle:

- IBKR live account state.
- IBKR commissions in the V2 allocation table.
- Hong Kong tax treatment.
- Currency conversion.
- Earnings dates.
- Regulatory filings.
- Fundamentals or valuation.
- Analyst revisions.
- Current news.
- Portfolio margin.
- Borrow costs.
- Real-time liquidity.

Because of that, this report should be treated as a technically grounded research plan, not a fully institutional trade ticket.

## How To Reproduce The Workflow

V2 recommendation scan:

```bash
quant recommend-v2 --from-date 2018-01-01 --to-date 2026-05-09 --top-n 12 --json-output
```

V1 historical simulation used for context:

```bash
quant paper-sim \
  --tickers SPY,QQQ,NVDA,AVGO,AMAT,MS,WMT,COST,IWM \
  --from-date 2018-01-01 \
  --to-date 2026-05-09 \
  --strategy momentum \
  --capital 20000 \
  --max-positions 5 \
  --commission-bps 0 \
  --slippage-bps 2 \
  --max-volume-participation 0.025 \
  --json-output
```

Allocation policy:

```python
from quant.technical_v2 import DEFAULT_RECOMMENDATION_UNIVERSE, latest_recommendations
from quant.allocation import allocate_from_recommendations

v2 = latest_recommendations(
    DEFAULT_RECOMMENDATION_UNIVERSE,
    "2018-01-01",
    "2026-05-09",
    top_n=25,
)
allocation = allocate_from_recommendations(v2["recommendations"], 20_000)
```

## Integrity Notes

The app is now more robust than the earlier recommendation path because:

- V2 has calibrated weights instead of arbitrary point scores.
- V2 exposes the exact feature table.
- V2 uses weekly trend confirmation.
- V2 includes ADX and moving-average slope.
- V2 includes relative volume and breakout pressure.
- V2 flags RSI divergence.
- Stops and targets are entry-specific.
- The allocation layer can reject overextended names.
- The report keeps cash when the available setups are not clean enough.

Remaining integrity limits:

- The data source is still Yahoo/yfinance.
- The default universe is not survivorship-bias-free.
- The current recommendation path is daily-bar based, not intraday.
- The allocation policy is explicit, but not yet optimized from a separate walk-forward portfolio allocation study.
- V2 has positive walk-forward evidence, but the signal is modest and should be used with risk controls.

## Final Recommendation

For a USD 20,000 research sleeve today, the app recommends **staged pullback entries**, not immediate full deployment.

Recommended posture:

- Allocate up to $17,113.01 across the selected names if pullback entries trigger.
- Keep $2,886.99 in cash.
- Do not chase excluded overbought semiconductor names.
- Re-run the scan after large market moves, major earnings, or broad index deterioration.
- If using a live broker later, route this through paper or manual-approval mode first.

The highest-conviction conclusion is not “buy everything.” The highest-conviction conclusion is:

```text
The market has strong technical leadership, but much of it is extended.
Use calibrated ranking, sector caps, pullback entries, and cash reserve.
```
