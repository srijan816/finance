# Technical Recommendation Path

This document explains how Quant Lab produced the May 2026 technical watchlist and the sample $20,000 allocation plan. It is a transparent decision trace, not investment advice.

## 1. Objective

The task was to answer:

- Which liquid U.S. stocks or ETFs look technically strongest today?
- Which prices are preferable for entry instead of chasing?
- Where should stops and first profit targets sit?
- How should a $20,000 paper/research allocation be staged?

The answer was generated from price/volume technical analysis only. It did not use fundamentals, analyst estimates, earnings revisions, macro data, options flow, insider data, or news sentiment.

## 2. Data Pull

The scan used daily adjusted OHLCV data from `yfinance` through May 8, 2026.

The scanned universe included broad ETFs, sector ETFs, and liquid large-cap equities:

- Broad ETFs: `SPY`, `QQQ`, `DIA`, `IWM`, `VTI`, `VOO`
- Sector/theme ETFs: `XLK`, `XLF`, `XLE`, `XLV`, `XLI`, `XLY`, `XLP`, `XLU`, `SMH`, `SOXX`, `IBB`, `GLD`, `TLT`
- Liquid equities: mega-cap technology, semiconductors, payments, healthcare, financials, industrials, consumer staples/discretionary, and selected high-beta growth names.

The scan required enough history to calculate at least a 200-day moving average and medium-term momentum. Symbols with insufficient history were skipped.

## 3. Indicators Computed

For each symbol, the app computed:

- Latest adjusted close.
- 20-day simple moving average.
- 50-day simple moving average.
- 200-day simple moving average.
- 21-trading-day return, roughly one month.
- 63-trading-day return, roughly one quarter.
- 126-trading-day return, roughly six months.
- 14-day RSI.
- 14-day ATR.
- 20-day high.
- 20-day low.
- 55-day high.
- 20-day average dollar volume.

These were used to classify trend, momentum, entry quality, and risk distance.

## 4. Trend Filter

A symbol was considered to be in a technical uptrend when:

```text
latest close > 200-day SMA
and
20-day SMA > 50-day SMA
```

This intentionally biases the model toward stocks already in confirmed positive trend. It avoids trying to pick bottoms.

## 5. Ranking Score

Each symbol received a score from trend, momentum, RSI, and liquidity:

```text
+25 if latest close > 200-day SMA, else -15
+20 if 20-day SMA > 50-day SMA, else -10
+20 if 50-day SMA > 200-day SMA
+ clipped 63-day momentum contribution
+ clipped 126-day momentum contribution
+10 if RSI is in the healthy trend range, roughly 45-65
-10 if RSI is very overbought, above roughly 75
-5 if RSI is weak, below roughly 35
-25 if average dollar volume is too low
```

This favors liquid symbols with strong intermediate-term momentum and a confirmed moving-average trend. It penalizes weak trends, very overextended RSI, and low liquidity.

## 6. Entry Classification

The app generated two possible entry styles:

### Pullback Entry

A pullback entry was considered attractive when:

```text
trend is positive
latest close is not more than about 3% above the 20-day SMA
latest close is not meaningfully below the 50-day SMA
RSI is roughly 42-68
```

This catches strong names that have cooled off enough to enter without chasing.

### Breakout Entry

A breakout entry was considered attractive when:

```text
trend is positive
latest close is near the 20-day high
RSI is roughly 45-75
```

This catches names pressing into new short-term highs without being absurdly extended.

## 7. Entry Prices

For every candidate, the app estimated two entry prices:

```text
preferred pullback entry = min(latest close, 20-day SMA + 0.25 * ATR)
breakout entry = 20-day high + 0.10 * ATR
```

The pullback price is designed to avoid paying too far above the short-term trend. The breakout price is designed to require confirmation above recent resistance.

## 8. Stop Logic

The initial version of this document showed one stop per ticker. That was too coarse because the same ticker can have two different entry contexts:

- A lower pullback entry.
- A higher breakout entry.

A stop must be calculated against the actual entry being used. Otherwise the document can show an invalid combination, such as a pullback buy price below the listed stop.

The corrected entry-specific stop logic is:

```text
support_stop = 50-day SMA - 0.25 * ATR
volatility_stop(entry) = entry - 2.2 * ATR
entry_stop = max(support_stop, volatility_stop(entry))
```

If that stop would sit above the current price, the model falls back to:

```text
entry_stop = entry - 2.2 * ATR
```

This creates a volatility-aware stop for each entry price. High-volatility names naturally receive wider stops; low-volatility names receive tighter stops.

## 9. First Target Logic

The first target used a simple reward/risk relationship:

```text
target_1(entry) = entry + 2.0 * (entry - entry_stop)
```

That means the first target is roughly a 2R move from the chosen entry price to the chosen stop. It is not a prediction of fair value; it is a trade-management level.

## 10. Trailing Exit Logic

After a position reaches its first target, the recommended management rule was:

- Sell 25-40% of the position at target 1.
- Move the remaining stop to breakeven or just under the 20-day moving average.
- Trail the remainder using the 50-day moving average or about 3 ATR below price.

This is meant to protect capital while leaving room for longer trend continuation.

## 11. Candidate Results

The highest-ranked names from the scan were heavily concentrated in semiconductors and high-momentum technology.

Top technical scores included:

| Ticker | Technical Read |
|---|---|
| `AMAT` | Strongest score; high 3-month and 6-month momentum; breakout setup. |
| `AVGO` | Strong trend; AI/semi leadership; breakout setup. |
| `NVDA` | Uptrend intact; less overextended than some semiconductor ETFs. |
| `MS` | Cleaner pullback/breakout profile; less overheated RSI. |
| `WMT` | Defensive uptrend; lower volatility; cleaner risk profile. |
| `IWM` | Small-cap breadth exposure; trend positive. |
| `COST` | High-quality defensive growth; tight setup. |
| `SPY` | Broad market exposure; positive trend but somewhat extended. |

Very strong names such as `MU`, `SMH`, `SOXX`, `AMD`, `INTC`, and `QCOM` were also high-scoring, but several showed very high RSI or large short-term extension. The interpretation layer therefore preferred a more balanced list instead of concentrating all capital in the most overheated semiconductor names.

## 12. Allocation Logic

The allocation plan used these principles:

- Avoid putting the full $20,000 into one sector.
- Keep some cash available because many top-ranked names were extended.
- Use fractional shares if the broker supports them.
- Favor 6-8 positions rather than 15-20 small ones.
- Keep estimated per-position loss tolerable if stops are hit.

The proposed allocation was:

| Ticker | Role | Allocation |
|---|---:|---:|
| `AMAT` | Semiconductor equipment momentum | $2,500 |
| `AVGO` | AI/semi infrastructure leader | $2,500 |
| `NVDA` | AI/semi momentum leader | $2,500 |
| `MS` | Financial trend exposure | $2,000 |
| `WMT` | Defensive consumer trend | $2,000 |
| `IWM` | Small-cap breadth exposure | $2,000 |
| `COST` | Quality defensive growth | $2,000 |
| `SPY` | Core broad-market exposure | $2,500 |
| Cash | Dry powder | $2,000 |

Total planned deployment: $18,000.

Cash reserve: $2,000.

## 13. Suggested Entry/Exit Levels

The corrected table separates pullback and breakout trade plans. A pullback entry must use the pullback stop and pullback target. A breakout entry must use the breakout stop and breakout target.

| Ticker | Latest | Pullback Buy | Pullback Stop | Pullback Target | Breakout Buy | Breakout Stop | Breakout Target | Allocation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `AMAT` | $433.60 | $404.81 | $368.69 | $477.06 | $435.32 | $397.39 | $511.18 | $2,500 |
| `AVGO` | $430.27 | $413.98 | $380.63 | $480.66 | $431.78 | $398.44 | $498.46 | $2,500 |
| `NVDA` | $215.23 | $205.02 | $188.83 | $237.42 | $217.35 | $201.15 | $249.74 | $2,500 |
| `MS` | $191.37 | $189.37 | $180.59 | $206.92 | $193.75 | $184.97 | $211.30 | $2,000 |
| `WMT` | $130.93 | $129.33 | $125.60 | $136.79 | $132.26 | $127.23 | $142.33 | $2,000 |
| `IWM` | $283.48 | $277.24 | $267.57 | $296.58 | $287.24 | $277.57 | $306.58 | $2,000 |
| `COST` | $1,012.81 | $1,004.77 | $993.15 | $1,028.02 | $1,018.19 | $993.15 | $1,068.28 | $2,000 |
| `SPY` | $736.97 | $714.79 | $699.34 | $745.67 | $737.68 | $722.23 | $768.56 | $2,500 |

The model does not require all positions to trigger. If only a few names reach acceptable entries, the remaining capital stays in cash.

## 13.1 SPY Stop-Loss Integrity Check

The original SPY row showed:

```text
preferred pullback buy: about $715
initial stop: about $721.50
```

That is invalid if the trade is entered at the pullback price, because a long-position stop must sit below the entry. The underlying SPY data was not the problem. The reproduced calculation was:

```text
latest close: 736.95
20-day SMA: 713.03
50-day SMA: 683.72
200-day SMA: 670.55
14-day ATR: 7.02
20-day high: 736.95
pullback entry: 714.78
breakout entry: 737.65
old stop: 721.51
```

The old stop was effectively a current-price/breakout-context stop:

```text
736.95 - 2.2 * 7.02 = 721.51
```

That is valid for a breakout-style entry near $738, but invalid for a pullback entry near $715. The corrected SPY trade plans are:

```text
SPY pullback plan:
entry = 714.79
stop = 699.34
target = 745.67

SPY breakout plan:
entry = 737.68
stop = 722.23
target = 768.56
```

The root cause was not corrupted price data. It was a methodology bug in the explanation layer: one stop and one target were displayed beside two different possible entries. The fix is to calculate stops and targets per entry scenario.

## 14. Portfolio-Level Risk Control

The interpretation layer added portfolio-level rules:

- Do not deploy all capital at once if most candidates are overbought.
- Do not force a buy if price is between the preferred pullback level and breakout trigger.
- If `SPY` closes below its 200-day moving average, reduce all equity exposure by 30-50%.
- If several semiconductor names fail stops together, do not immediately re-enter the same sector.
- Re-run the scan after major earnings, Fed decisions, or large market gaps.

## 15. Why The Recommendation Was Not “Buy Everything Now”

The score table was strong, but many leading names were already extended:

- Semiconductor ETFs and several chip names had very strong 1-month and 3-month moves.
- Some RSI readings were above the range where the model prefers fresh entries.
- The highest-scoring sector cluster was semiconductors, creating concentration risk.

For that reason, the final recommendation used staged entries, stops, and cash reserve rather than immediate full deployment.

## 16. What The Model Is Good At Here

This process is reasonably useful for:

- Finding liquid names in confirmed uptrends.
- Ranking momentum leadership.
- Avoiding obvious technical weakness.
- Converting a watchlist into entries, stops, and targets.
- Keeping a paper-trading plan auditable.

## 17. What The Model Is Not Yet Doing

The current recommendation does not yet include:

- Fundamentals.
- Earnings date risk.
- Forward guidance or analyst revisions.
- Valuation.
- News sentiment.
- Options positioning.
- Real-time order-book liquidity.
- Intraday support/resistance.
- Tax, FX, or jurisdiction-specific constraints.

Therefore, this is a technically grounded research plan, not a complete institutional investment process.

## 18. Audit Summary

The path was:

```text
fresh daily OHLCV data
-> compute SMA, momentum, RSI, ATR, highs/lows, liquidity
-> filter for positive trend
-> rank by trend + momentum + RSI + liquidity
-> classify pullback and breakout setups
-> calculate entries, stops, and first targets
-> diversify across sectors and ETFs
-> reserve cash due to extension risk
-> define sell and risk-management rules
```

The final plan was deliberately more conservative than the raw score ranking because the highest-ranked cluster was concentrated and partially overbought.
