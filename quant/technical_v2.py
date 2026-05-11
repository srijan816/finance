"""Calibrated technical recommendation engine.

This module keeps the earlier heuristic screener intact and adds a transparent
feature model whose weights are fit from historical forward active returns.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from typing import Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

from quant.recommendations import EntryPlan, long_entry_plan
from quant.research_status import research_grade_status
from quant.validation_purged import purged_walk_forward_splits, score_prediction_folds


DEFAULT_RECOMMENDATION_UNIVERSE = [
    "SPY", "QQQ", "IWM", "VOO", "VTI", "SMH", "SOXX", "XLK", "XLF", "XLE", "XLV", "XLI",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "JPM", "V", "MA",
    "LLY", "UNH", "XOM", "COST", "WMT", "HD", "PG", "JNJ", "ORCL", "NFLX", "AMD",
    "CRM", "ADBE", "CSCO", "INTC", "BAC", "KO", "PEP", "MCD", "DIS", "PFE", "CVX",
    "GE", "IBM", "T", "MRK", "ABBV", "NKE", "CAT", "BA", "GS", "MS", "NOW", "QCOM",
    "TXN", "AMAT", "MU", "PANW", "SHOP", "UBER", "PLTR", "COIN",
]

FEATURE_NAMES = [
    "mom_21",
    "mom_63",
    "mom_126",
    "price_vs_sma200",
    "sma20_vs_sma50",
    "sma50_vs_sma200",
    "sma50_slope_20",
    "sma200_slope_40",
    "adx_14",
    "di_spread",
    "rsi_14",
    "rsi_extension",
    "rel_volume_20",
    "breakout_pressure",
    "atr_pct",
    "weekly_price_vs_sma40",
    "weekly_sma10_vs_sma40",
    "weekly_sma40_slope",
    "price_position_20",
    "bearish_rsi_divergence",
    "bullish_rsi_divergence",
]


@dataclass
class CalibratedModel:
    coefficients: np.ndarray
    intercept: float
    mean: np.ndarray
    scale: np.ndarray
    feature_names: list[str]
    ridge_alpha: float

    def predict_one(self, values: Sequence[float]) -> float:
        x = (np.asarray(values, dtype=float) - self.mean) / self.scale
        return float(self.intercept + x @ self.coefficients)

    def coefficient_table(self) -> dict:
        return {
            name: round(float(value), 6)
            for name, value in zip(self.feature_names, self.coefficients)
        }


def bars_to_frame(bars: Sequence[tuple]) -> pd.DataFrame:
    df = pd.DataFrame(bars, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates("date").sort_values("date").set_index("date")
    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna(subset=["close"])


def technical_feature_frame(bars: Sequence[tuple]) -> pd.DataFrame:
    df = bars_to_frame(bars)
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    features = pd.DataFrame(index=df.index)
    features["close"] = close
    features["sma20"] = close.rolling(20).mean()
    features["sma50"] = close.rolling(50).mean()
    features["sma200"] = close.rolling(200).mean()
    features["mom_21"] = close.pct_change(21)
    features["mom_63"] = close.pct_change(63)
    features["mom_126"] = close.pct_change(126)
    features["price_vs_sma200"] = close / features["sma200"] - 1
    features["sma20_vs_sma50"] = features["sma20"] / features["sma50"] - 1
    features["sma50_vs_sma200"] = features["sma50"] / features["sma200"] - 1
    features["sma50_slope_20"] = features["sma50"] / features["sma50"].shift(20) - 1
    features["sma200_slope_40"] = features["sma200"] / features["sma200"].shift(40) - 1
    features["rsi_14"] = rsi(close, 14)
    features["rsi_extension"] = (features["rsi_14"] - 55).abs() / 50
    features["atr_14"] = atr(high, low, close, 14)
    features["atr_pct"] = features["atr_14"] / close
    adx_frame = adx(high, low, close, 14)
    features["adx_14"] = adx_frame["adx"] / 100
    features["di_spread"] = (adx_frame["plus_di"] - adx_frame["minus_di"]) / 100
    avg_volume_20 = volume.rolling(20).mean()
    features["rel_volume_20"] = volume / avg_volume_20
    prior_high20 = close.shift(1).rolling(20).max()
    features["high20_prior"] = prior_high20
    features["high20"] = close.rolling(20).max()
    features["low20"] = close.rolling(20).min()
    features["breakout_pressure"] = close / prior_high20 - 1
    range20 = features["high20"] - features["low20"]
    features["price_position_20"] = (close - features["low20"]) / range20.replace(0, np.nan)
    weekly = weekly_features(df)
    features = features.join(weekly, how="left").ffill()
    divergence = rsi_divergence(close, features["rsi_14"])
    features["bearish_rsi_divergence"] = divergence["bearish"]
    features["bullish_rsi_divergence"] = divergence["bullish"]
    return features.replace([np.inf, -np.inf], np.nan)


def latest_recommendations(
    tickers: Sequence[str],
    start: str,
    end: str,
    benchmark: str = "SPY",
    horizon: int = 63,
    top_n: int = 10,
    ridge_alpha: float = 5.0,
) -> dict:
    """Fetch data, calibrate feature weights, and produce current recommendations."""
    from quant.data import fetch_bars

    bars_by_ticker = {ticker.upper(): fetch_bars(ticker.upper(), start, end) for ticker in tickers}
    benchmark_bars = fetch_bars(benchmark, start, end)
    return recommend_from_bars(
        bars_by_ticker,
        benchmark_bars,
        benchmark=benchmark,
        horizon=horizon,
        top_n=top_n,
        ridge_alpha=ridge_alpha,
    )


def recommend_from_bars(
    bars_by_ticker: Dict[str, Sequence[tuple]],
    benchmark_bars: Sequence[tuple],
    benchmark: str = "SPY",
    horizon: int = 63,
    top_n: int = 10,
    ridge_alpha: float = 5.0,
) -> dict:
    feature_frames = {
        ticker: technical_feature_frame(bars)
        for ticker, bars in bars_by_ticker.items()
        if len(bars) >= 260
    }
    benchmark_frame = bars_to_frame(benchmark_bars)
    samples = build_training_samples(feature_frames, benchmark_frame, horizon=horizon)
    if len(samples) < 50:
        raise ValueError(f"not enough calibration samples: {len(samples)}")

    x = samples[FEATURE_NAMES].to_numpy(dtype=float)
    y = samples["forward_active_return"].to_numpy(dtype=float)
    model = fit_ridge_model(x, y, ridge_alpha=ridge_alpha)
    legacy_validation = walk_forward_validate_samples(samples, ridge_alpha=ridge_alpha)
    validation = purged_walk_forward_validate_samples(samples, ridge_alpha=ridge_alpha, horizon=horizon)

    recommendations = []
    for ticker, frame in feature_frames.items():
        latest = frame.dropna(subset=FEATURE_NAMES + ["close", "atr_14", "sma50"]).tail(1)
        if latest.empty:
            continue
        row = latest.iloc[0]
        values = row[FEATURE_NAMES].to_numpy(dtype=float)
        prediction = model.predict_one(values)
        gates = setup_gates(row)
        pullback, breakout = entry_plans(row, ticker=ticker)
        recommendations.append({
            "ticker": ticker,
            "as_of": str(latest.index[-1].date()),
            "price": round(float(row["close"]), 2),
            "predicted_63d_active_return": round(prediction, 4),
            "rank_score": round(prediction * gates["quality_multiplier"], 4),
            "quality_multiplier": gates["quality_multiplier"],
            "gates": gates,
            "features": feature_snapshot(row),
            "pullback_plan": plan_to_dict(pullback),
            "breakout_plan": plan_to_dict(breakout),
        })

    recommendations.sort(key=lambda item: item["rank_score"], reverse=True)
    return {
        "benchmark": benchmark,
        "horizon_days": horizon,
        "model": {
            "type": "standardized_ridge_regression",
            "target": f"{horizon}-trading-day forward active return vs {benchmark}",
            "ridge_alpha": ridge_alpha,
            "feature_names": FEATURE_NAMES,
            "coefficients": model.coefficient_table(),
        },
        "validation": validation,
        "legacy_validation": legacy_validation,
        "recommendations": recommendations[:top_n],
        "audit": {
            "n_calibration_samples": int(len(samples)),
            "n_symbols_scanned": int(len(feature_frames)),
            "non_arbitrary_ranking": "Final ranks are learned from historical forward active returns, not hand-weighted points.",
            "lookahead_control": "Each training row uses features at date T and a target from T to T+horizon; current recommendations use only data available through the latest bar.",
        },
        "research_grade_status": research_grade_status(
            data_source="norgate_ascii_import" if os.getenv("QUANT_DATA_SOURCE", "").strip().lower() == "norgate" else "yfinance",
            universe_name="current_or_user_supplied_ticker_list",
            validation_method="purged_walk_forward_with_embargo",
            has_purged_validation=True,
            has_cpcv=False,
            has_dsr_pbo=True,
            has_risk_optimizer=False,
            has_execution_shortfall=False,
            feature_sources=["price_volume"],
            notes=[
                "V2 is calibrated, but current validation is not purged/embargoed and the universe is not verified survivorship-bias-free.",
            ],
        ),
    }


def build_training_samples(
    feature_frames: Dict[str, pd.DataFrame],
    benchmark_frame: pd.DataFrame,
    horizon: int = 63,
    step: int = 21,
) -> pd.DataFrame:
    benchmark_close = benchmark_frame["close"]
    rows = []
    for ticker, frame in feature_frames.items():
        joined = frame.join(benchmark_close.rename("benchmark_close"), how="inner")
        joined["label_start_date"] = joined.index
        joined["label_end_date"] = joined.index.to_series().shift(-horizon)
        joined["future_return"] = joined["close"].shift(-horizon) / joined["close"] - 1
        joined["future_benchmark_return"] = joined["benchmark_close"].shift(-horizon) / joined["benchmark_close"] - 1
        joined["forward_active_return"] = joined["future_return"] - joined["future_benchmark_return"]
        usable = joined.dropna(subset=FEATURE_NAMES + ["forward_active_return", "label_end_date"])
        usable = usable.iloc[::step].copy()
        usable["ticker"] = ticker
        usable["sample_date"] = usable.index
        rows.append(usable[["ticker", "sample_date", "label_start_date", "label_end_date", "forward_active_return"] + FEATURE_NAMES])
    if not rows:
        return pd.DataFrame(columns=["ticker", "sample_date", "label_start_date", "label_end_date", "forward_active_return"] + FEATURE_NAMES)
    return pd.concat(rows, axis=0, ignore_index=True)


def fit_ridge_model(x: np.ndarray, y: np.ndarray, ridge_alpha: float = 5.0) -> CalibratedModel:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mean = np.nanmean(x, axis=0)
    scale = np.nanstd(x, axis=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    z = (x - mean) / scale
    z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
    y_mean = float(np.mean(y))
    centered_y = y - y_mean
    penalty = ridge_alpha * np.eye(z.shape[1])
    coefficients = np.linalg.pinv(z.T @ z + penalty) @ z.T @ centered_y
    return CalibratedModel(coefficients, y_mean, mean, scale, FEATURE_NAMES.copy(), ridge_alpha)


def walk_forward_validate_samples(
    samples: pd.DataFrame,
    ridge_alpha: float = 5.0,
    min_train_samples: int = 250,
    test_window_samples: int = 80,
) -> dict:
    ordered = samples.sort_values("sample_date").reset_index(drop=True)
    folds = []
    start = min_train_samples
    while start + test_window_samples <= len(ordered):
        train = ordered.iloc[:start]
        test = ordered.iloc[start:start + test_window_samples]
        model = fit_ridge_model(train[FEATURE_NAMES].to_numpy(float), train["forward_active_return"].to_numpy(float), ridge_alpha)
        preds = np.asarray([model.predict_one(row) for row in test[FEATURE_NAMES].to_numpy(float)])
        actual = test["forward_active_return"].to_numpy(float)
        if len(np.unique(np.round(preds, 10))) <= 1:
            corr = 0.0
        else:
            corr = float(np.corrcoef(preds, actual)[0, 1])
        top_cut = np.quantile(preds, 0.8)
        top_actual = actual[preds >= top_cut]
        folds.append({
            "start": str(pd.to_datetime(test["sample_date"].iloc[0]).date()),
            "end": str(pd.to_datetime(test["sample_date"].iloc[-1]).date()),
            "rank_correlation": 0.0 if not np.isfinite(corr) else corr,
            "top_quintile_avg_active_return": float(np.mean(top_actual)) if len(top_actual) else 0.0,
            "all_avg_active_return": float(np.mean(actual)) if len(actual) else 0.0,
            "top_quintile_hit_rate": float(np.mean(top_actual > 0)) if len(top_actual) else 0.0,
        })
        start += test_window_samples

    if not folds:
        return {"n_folds": 0, "warning": "Not enough samples for walk-forward validation."}
    return {
        "n_folds": len(folds),
        "avg_rank_correlation": round(float(np.mean([fold["rank_correlation"] for fold in folds])), 4),
        "avg_top_quintile_active_return": round(float(np.mean([fold["top_quintile_avg_active_return"] for fold in folds])), 4),
        "avg_all_active_return": round(float(np.mean([fold["all_avg_active_return"] for fold in folds])), 4),
        "avg_top_quintile_hit_rate": round(float(np.mean([fold["top_quintile_hit_rate"] for fold in folds])), 4),
        "folds": folds[-5:],
    }


def purged_walk_forward_validate_samples(
    samples: pd.DataFrame,
    ridge_alpha: float = 5.0,
    horizon: int = 63,
    min_train_samples: int = 250,
    test_window_samples: int = 80,
) -> dict:
    folds = purged_walk_forward_splits(
        samples,
        horizon=horizon,
        min_train_samples=min_train_samples,
        test_window_samples=test_window_samples,
    )

    def fit_predict(train: pd.DataFrame, test: pd.DataFrame, feature_cols: Sequence[str]) -> np.ndarray:
        model = fit_ridge_model(train[list(feature_cols)].to_numpy(float), train["forward_active_return"].to_numpy(float), ridge_alpha)
        return np.asarray([model.predict_one(row) for row in test[list(feature_cols)].to_numpy(float)])

    scored = score_prediction_folds(folds, fit_predict, FEATURE_NAMES, target_col="forward_active_return")
    return {
        "method": "purged_walk_forward",
        "horizon_days": horizon,
        "embargo_days": max(10, int(np.ceil(horizon * 0.15))),
        "n_folds": scored["n_folds"],
        "avg_rank_correlation": scored["avg_rank_ic"],
        "median_rank_correlation": scored["median_rank_ic"],
        "folds": scored["folds"][-5:],
        "pbo": scored["pbo"],
        "dsr": scored["dsr"],
    }


def setup_gates(row: pd.Series) -> dict:
    daily_trend = bool(row["close"] > row["sma200"] and row["sma20"] > row["sma50"] and row["sma50_slope_20"] > 0)
    weekly_trend = bool(
        row["weekly_price_vs_sma40"] > 0
        and row["weekly_sma10_vs_sma40"] > 0
        and row["weekly_sma40_slope"] > 0
    )
    trend_strength = "strong" if row["adx_14"] >= 0.25 else "moderate" if row["adx_14"] >= 0.18 else "weak"
    volume_confirmed = bool(row["rel_volume_20"] >= 1.2 and row["breakout_pressure"] > 0)
    overbought = bool(row["rsi_14"] >= 75)
    bearish_divergence = bool(row["bearish_rsi_divergence"] > 0)
    multiplier = 1.0
    if not daily_trend:
        multiplier *= 0.35
    if not weekly_trend:
        multiplier *= 0.6
    if trend_strength == "weak":
        multiplier *= 0.75
    if overbought:
        multiplier *= 0.8
    if bearish_divergence:
        multiplier *= 0.75
    if volume_confirmed:
        multiplier *= 1.08
    return {
        "daily_trend": daily_trend,
        "weekly_trend": weekly_trend,
        "trend_strength": trend_strength,
        "volume_confirmed_breakout": volume_confirmed,
        "overbought_rsi": overbought,
        "bearish_rsi_divergence": bearish_divergence,
        "bullish_rsi_divergence": bool(row["bullish_rsi_divergence"] > 0),
        "quality_multiplier": round(multiplier, 4),
    }


def entry_plans(row: pd.Series, ticker: str = "") -> tuple[EntryPlan, EntryPlan]:
    atr_value = float(row["atr_14"])
    latest_close = float(row["close"])
    pullback_entry = min(float(row["close"]), float(row["sma20"] + 0.25 * atr_value))
    breakout_trigger = float(row["high20_prior"] + 0.10 * atr_value)
    breakout_entry = max(breakout_trigger, latest_close)
    support_stop = float(row["sma50"] - 0.25 * atr_value)
    atr_multiple, reward_risk = regime_risk_parameters(row, ticker=ticker)
    pullback = long_entry_plan(pullback_entry, atr_value, support_stop, reward_risk, atr_multiple)
    breakout = long_entry_plan(breakout_entry, atr_value, support_stop, reward_risk, atr_multiple)
    return pullback, breakout


def regime_risk_parameters(row: pd.Series, ticker: str = "") -> tuple[float, float]:
    atr_pct = float(row["atr_pct"])
    is_etf = ticker in {"SPY", "QQQ", "IWM", "VOO", "VTI", "SMH", "SOXX", "XLK", "XLF", "XLE", "XLV", "XLI"}
    if atr_pct < 0.018:
        atr_multiple = 1.8
        reward_risk = 1.8
    elif atr_pct < 0.035:
        atr_multiple = 2.2
        reward_risk = 2.0
    else:
        atr_multiple = 2.8
        reward_risk = 2.3
    if is_etf:
        atr_multiple = max(1.6, atr_multiple - 0.2)
    return atr_multiple, reward_risk


def feature_snapshot(row: pd.Series) -> dict:
    keys = [
        "mom_21", "mom_63", "mom_126", "price_vs_sma200", "sma20_vs_sma50",
        "sma50_slope_20", "adx_14", "di_spread", "rsi_14", "rel_volume_20",
        "breakout_pressure", "atr_pct", "weekly_price_vs_sma40",
        "weekly_sma10_vs_sma40", "weekly_sma40_slope",
    ]
    return {key: round(float(row[key]), 4) for key in keys}


def plan_to_dict(plan: EntryPlan) -> dict:
    return {
        "entry": round(float(plan.entry), 2),
        "stop": round(float(plan.stop), 2),
        "target": round(float(plan.target), 2),
        "risk_pct": round(float((plan.entry - plan.stop) / plan.entry), 4),
    }


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    result[(avg_loss == 0) & (avg_gain > 0)] = 100.0
    result[(avg_loss == 0) & (avg_gain == 0)] = 50.0
    return result


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    previous_close = close.shift(1)
    true_range = pd.concat([
        high - low,
        (high - previous_close).abs(),
        (low - previous_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.DataFrame:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    atr_values = atr(high, low, close, window)
    plus_di = 100 * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr_values
    minus_di = 100 * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr_values
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_values = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return pd.DataFrame({"adx": adx_values, "plus_di": plus_di, "minus_di": minus_di})


def weekly_features(df: pd.DataFrame) -> pd.DataFrame:
    weekly_close = df["close"].resample("W-FRI").last().dropna()
    weekly = pd.DataFrame(index=weekly_close.index)
    weekly["weekly_sma10"] = weekly_close.rolling(10).mean()
    weekly["weekly_sma40"] = weekly_close.rolling(40).mean()
    weekly["weekly_price_vs_sma40"] = weekly_close / weekly["weekly_sma40"] - 1
    weekly["weekly_sma10_vs_sma40"] = weekly["weekly_sma10"] / weekly["weekly_sma40"] - 1
    weekly["weekly_sma40_slope"] = weekly["weekly_sma40"] / weekly["weekly_sma40"].shift(8) - 1
    daily_index = df.index
    return weekly[["weekly_price_vs_sma40", "weekly_sma10_vs_sma40", "weekly_sma40_slope"]].reindex(daily_index, method="ffill")


def rsi_divergence(close: pd.Series, rsi_values: pd.Series, lookback: int = 60) -> pd.DataFrame:
    bearish = pd.Series(0.0, index=close.index)
    bullish = pd.Series(0.0, index=close.index)
    rolling_high_previous = close.shift(1).rolling(lookback).max()
    rolling_low_previous = close.shift(1).rolling(lookback).min()
    rsi_high_previous = rsi_values.shift(1).rolling(lookback).max()
    rsi_low_previous = rsi_values.shift(1).rolling(lookback).min()
    bearish[(close > rolling_high_previous) & (rsi_values < rsi_high_previous)] = 1.0
    bullish[(close < rolling_low_previous) & (rsi_values > rsi_low_previous)] = 1.0
    return pd.DataFrame({"bearish": bearish, "bullish": bullish})
