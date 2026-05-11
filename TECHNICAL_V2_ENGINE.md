# Technical V2 Engine

This document describes the upgraded technical recommendation engine. V2 exists beside the original heuristic engine, so existing backtests, simulations, reports, and CLI commands continue to work.

## Why V2 Exists

The original recommendation layer had several valid weaknesses:

- Hand-weighted scores such as `+25` and `+20`.
- Momentum clipping that was not fully documented.
- No volume confirmation beyond average dollar volume.
- No weekly trend confirmation.
- No ADX or moving-average slope trend-strength checks.
- Fixed ATR stop and reward/risk parameters.
- No RSI divergence detection.

V2 addresses these without deleting V1.

## Core Design

V2 is not a hand-score model. It builds a transparent feature table and fits a standardized ridge regression model to historical forward active returns.

The target is:

```text
forward_active_return =
  ticker_return(T -> T + horizon)
- benchmark_return(T -> T + horizon)
```

The default horizon is 63 trading days.

The default benchmark is `SPY`.

The ranking score is:

```text
rank_score = predicted_forward_active_return * quality_multiplier
```

The prediction comes from calibrated historical data. The quality multiplier comes from explicit risk gates such as weekly trend, ADX strength, RSI extension, volume confirmation, and divergence.

## Feature Set

The feature vector is:

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
| `adx_14` | Wilder ADX divided by 100 |
| `di_spread` | +DI minus -DI divided by 100 |
| `rsi_14` | Wilder-style RSI |
| `rsi_extension` | absolute distance from healthy trend RSI |
| `rel_volume_20` | current volume / 20-day average volume |
| `breakout_pressure` | close / prior 20-day high - 1 |
| `atr_pct` | 14-day ATR / close |
| `weekly_price_vs_sma40` | weekly close / 40-week SMA - 1 |
| `weekly_sma10_vs_sma40` | weekly 10-week SMA / 40-week SMA - 1 |
| `weekly_sma40_slope` | 8-week rate of change in 40-week SMA |
| `price_position_20` | close location inside 20-day high/low range |
| `bearish_rsi_divergence` | price high without RSI high |
| `bullish_rsi_divergence` | price low without RSI low |

## Calibration

V2 uses ridge regression because it is transparent, robust with correlated technical features, and does not need a black-box dependency.

The model standardizes every feature:

```text
z = (x - training_mean) / training_std
```

Then fits:

```text
forward_active_return = intercept + z @ coefficients
```

The ridge penalty prevents unstable coefficients when features overlap, which is common in technical analysis.

## Walk-Forward Validation

The engine validates by repeatedly:

1. Training on earlier samples.
2. Predicting the next out-of-sample window.
3. Measuring rank correlation, top-quintile active return, average active return, and top-quintile hit rate.

This does not prove future returns, but it is much better than fitting weights and reporting in-sample performance.

## Weekly Confirmation

The weekly trend gate checks:

```text
weekly close > weekly 40-SMA
weekly 10-SMA > weekly 40-SMA
weekly 40-SMA slope > 0
```

If this fails, the quality multiplier is reduced. The trade can still appear if the calibrated prediction is high, but the rank is penalized.

## Trend Strength

ADX is used as a trend-strength classifier:

```text
ADX >= 25: strong trend
ADX >= 18: moderate trend
else: weak trend
```

Weak trend setups are penalized.

## Volume Confirmation

Breakout volume is confirmed when:

```text
relative_volume_20 >= 1.2
and
breakout_pressure > 0
```

This means a breakout has more credibility when price is pressing above the prior 20-day high on above-normal volume.

## RSI Divergence

V2 flags:

- Bearish divergence: price makes a lookback high while RSI does not.
- Bullish divergence: price makes a lookback low while RSI does not.

Bearish divergence reduces the quality multiplier. Bullish divergence is exposed for audit but is not enough by itself to override trend weakness.

## Regime-Aware Stops

V2 no longer uses one fixed ATR multiple for every symbol.

The ATR multiple depends on volatility regime:

```text
ATR / price < 1.8%: low volatility
ATR / price < 3.5%: normal volatility
otherwise: high volatility
```

The stop calculation is entry-specific:

```text
support_stop = 50-day SMA - 0.25 * ATR
volatility_stop(entry) = entry - atr_multiple * ATR
entry_stop = max(support_stop, volatility_stop(entry))
```

If `entry_stop` would be above the entry, V2 falls back to:

```text
entry_stop = entry - atr_multiple * ATR
```

This prevents the earlier SPY issue where a pullback entry was shown with a breakout-context stop.

## Entry Plans

V2 emits two separate plans:

```text
pullback_entry = min(close, 20-day SMA + 0.25 * ATR)
breakout_entry = max(prior 20-day high + 0.10 * ATR, close)
```

Each plan has its own stop and target.

## CLI Usage

```bash
quant recommend-v2 --tickers SPY,QQQ,NVDA,AVGO,AMAT,MS,WMT,COST,IWM --from-date 2018-01-01 --to-date 2026-05-09 --top-n 5
```

JSON output:

```bash
quant recommend-v2 --tickers SPY,QQQ,NVDA --json-output
```

The command reports:

- Number of calibration samples.
- Walk-forward validation summary.
- Predicted active return.
- Rank score.
- Pullback entry/stop.
- Breakout entry/stop.
- Weekly trend state.
- ADX trend strength.
- Volume breakout confirmation.

## Current Smoke Test

On a focused universe through May 9, 2026:

```text
samples = 774
walk-forward folds = 6
average top-quintile active return = 8.58%
```

Top names in that run included `AMAT`, `AVGO`, `NVDA`, `COST`, and `WMT`.

This is a smoke test, not a production investment claim. It still needs larger universe tests with survivorship-bias-free data.

## Files

- Engine: `quant/technical_v2.py`
- Entry plan helper: `quant/recommendations.py`
- CLI command: `quant recommend-v2`
- Tests: `tests/test_technical_v2.py`, `tests/test_recommendations.py`
