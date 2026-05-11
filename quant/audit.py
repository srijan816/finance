"""Historical decision audits under a veil-of-ignorance protocol."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import numpy as np

from quant.research_status import research_grade_status
from quant.stats import binomial_p_value, mean_confidence_interval, mean_z_test
from quant.strategies import signal_for_strategy


@dataclass(frozen=True)
class HistoricalDecision:
    ticker: str
    decision_date: str
    entry_date: str
    exit_date: str
    decision: str
    confidence: float
    forward_return: float
    benchmark_return: float | None
    active_return: float | None
    decision_edge: float
    correct: bool

    def to_dict(self) -> Dict:
        return {
            "ticker": self.ticker,
            "decision_date": self.decision_date,
            "entry_date": self.entry_date,
            "exit_date": self.exit_date,
            "decision": self.decision,
            "confidence": round(self.confidence, 4),
            "forward_return": round(self.forward_return * 100, 3),
            "benchmark_return": None if self.benchmark_return is None else round(self.benchmark_return * 100, 3),
            "active_return": None if self.active_return is None else round(self.active_return * 100, 3),
            "decision_edge": round(self.decision_edge * 100, 3),
            "correct": bool(self.correct),
        }


def audit_historical_decisions(
    ticker: str,
    start: str,
    end: str,
    strategy: str = "sma_cross",
    benchmark: str = "SPY",
    min_history: int = 252,
    horizon: int = 21,
    step: int = 21,
    target: str = "benchmark",
    neutral_band_bps: float = 25.0,
) -> Dict:
    """Replay historical decisions using only data known before each decision."""
    from quant.data import fetch_bars

    bars = fetch_bars(ticker, start, end)
    if len(bars) < min_history + horizon + 1:
        return {
            "ticker": ticker,
            "error": f"Need at least {min_history + horizon + 1} bars, got {len(bars)}",
        }

    benchmark_bars = []
    if benchmark:
        try:
            benchmark_bars = fetch_bars(benchmark, start, end)
        except Exception:
            benchmark_bars = []

    decisions = generate_historical_decisions(
        ticker=ticker,
        bars=bars,
        strategy=strategy,
        benchmark_bars=benchmark_bars,
        min_history=min_history,
        horizon=horizon,
        step=step,
        target=target,
        neutral_band_bps=neutral_band_bps,
    )

    return {
        "ticker": ticker,
        "strategy": strategy,
        "benchmark": benchmark if benchmark_bars else None,
        "target": target,
        "min_history": min_history,
        "horizon": horizon,
        "step": step,
        "summary": summarize_decisions(decisions),
        "decisions": [decision.to_dict() for decision in decisions],
        "protocol": {
            "veil_of_ignorance": "Decision at T uses bars strictly before T, enters on the next bar, then evaluates forward returns.",
            "neutral_band_bps": neutral_band_bps,
            "data_note": "Historical OHLCV quality depends on the configured data provider.",
        },
        "research_grade_status": research_grade_status(
            data_source="yfinance",
            universe_name=ticker,
            validation_method="historical_decision_audit_prior_information",
            feature_sources=["price_volume"],
            notes=[
                "Decision timing is prior-information-only, but data and universe bias controls are not production-grade.",
            ],
        ),
    }


def audit_universe_decisions(
    tickers: Sequence[str],
    start: str,
    end: str,
    strategy: str = "sma_cross",
    benchmark: str = "SPY",
    min_history: int = 252,
    horizon: int = 21,
    step: int = 21,
    target: str = "benchmark",
    neutral_band_bps: float = 25.0,
) -> Dict:
    """Run the veil-of-ignorance audit across a ticker universe."""
    from quant.data import fetch_bars

    benchmark_bars = []
    if benchmark:
        try:
            benchmark_bars = fetch_bars(benchmark, start, end)
        except Exception:
            benchmark_bars = []

    per_ticker = {}
    all_decisions = []
    for ticker in tickers:
        try:
            bars = fetch_bars(ticker, start, end)
            if len(bars) < min_history + horizon + 1:
                per_ticker[ticker] = {
                    "error": f"Need at least {min_history + horizon + 1} bars, got {len(bars)}",
                }
                continue
            decisions = generate_historical_decisions(
                ticker=ticker,
                bars=bars,
                strategy=strategy,
                benchmark_bars=benchmark_bars,
                min_history=min_history,
                horizon=horizon,
                step=step,
                target=target,
                neutral_band_bps=neutral_band_bps,
            )
            all_decisions.extend(decisions)
            per_ticker[ticker] = summarize_decisions(decisions)
        except Exception as exc:
            per_ticker[ticker] = {"error": str(exc)}

    return {
        "tickers": list(tickers),
        "strategy": strategy,
        "benchmark": benchmark if benchmark_bars else None,
        "target": target,
        "min_history": min_history,
        "horizon": horizon,
        "step": step,
        "summary": summarize_decisions(all_decisions),
        "per_ticker": per_ticker,
        "protocol": {
            "veil_of_ignorance": "Each ticker decision at T uses bars strictly before T, enters on the next bar, then evaluates forward returns.",
            "neutral_band_bps": neutral_band_bps,
            "data_note": "Historical OHLCV quality depends on the configured data provider.",
        },
        "research_grade_status": research_grade_status(
            data_source="yfinance",
            universe_name="user_supplied_tickers",
            validation_method="historical_universe_decision_audit_prior_information",
            feature_sources=["price_volume"],
            notes=[
                "Decision timing is prior-information-only, but the supplied universe may be survivorship-biased.",
            ],
        ),
    }


def generate_historical_decisions(
    ticker: str,
    bars: Sequence[tuple],
    strategy: str,
    benchmark_bars: Sequence[tuple] | None = None,
    min_history: int = 252,
    horizon: int = 21,
    step: int = 21,
    target: str = "benchmark",
    neutral_band_bps: float = 25.0,
) -> List[HistoricalDecision]:
    dates = [row[0] for row in bars]
    closes = np.asarray([row[4] for row in bars], dtype=float)
    benchmark_closes = np.asarray([row[4] for row in benchmark_bars or []], dtype=float)
    neutral_band = neutral_band_bps / 10_000

    decisions = []
    for entry_idx in range(min_history, len(closes) - horizon, step):
        history = closes[:entry_idx]
        signal = signal_for_strategy(strategy, history)
        position = float(signal[-1]) if len(signal) else 0.0
        decision = "BUY" if position > 0 else "HOLD"
        confidence = _decision_confidence(strategy, history, decision)

        exit_idx = entry_idx + horizon
        forward_return = closes[exit_idx] / closes[entry_idx] - 1
        benchmark_return = _benchmark_forward_return(benchmark_closes, entry_idx, exit_idx)
        active_return = None if benchmark_return is None else forward_return - benchmark_return
        score_return = active_return if target == "benchmark" and active_return is not None else forward_return
        correct = _decision_correct(decision, score_return, neutral_band)
        decision_edge = score_return if decision == "BUY" else -score_return

        decisions.append(HistoricalDecision(
            ticker=ticker,
            decision_date=dates[entry_idx - 1],
            entry_date=dates[entry_idx],
            exit_date=dates[exit_idx],
            decision=decision,
            confidence=confidence,
            forward_return=float(forward_return),
            benchmark_return=benchmark_return,
            active_return=active_return,
            decision_edge=float(decision_edge),
            correct=correct,
        ))
    return decisions


def summarize_decisions(decisions: Sequence[HistoricalDecision]) -> Dict:
    if not decisions:
        return {"n_decisions": 0}

    correctness = np.asarray([d.correct for d in decisions], dtype=float)
    confidence = np.asarray([d.confidence for d in decisions], dtype=float)
    forward = np.asarray([d.forward_return for d in decisions], dtype=float)
    edge = np.asarray([d.decision_edge for d in decisions], dtype=float)
    edge_ci = mean_confidence_interval(edge)
    edge_test = mean_z_test(edge)
    successes = int(correctness.sum())
    active_values = [d.active_return for d in decisions if d.active_return is not None]
    active = np.asarray(active_values, dtype=float) if active_values else np.asarray([], dtype=float)
    buys = [d for d in decisions if d.decision == "BUY"]
    holds = [d for d in decisions if d.decision == "HOLD"]

    return {
        "n_decisions": len(decisions),
        "accuracy": round(float(correctness.mean()) * 100, 2),
        "accuracy_p_value": round(binomial_p_value(successes, len(decisions)), 4),
        "brier_score": round(float(np.mean((confidence - correctness) ** 2)), 4),
        "avg_confidence": round(float(confidence.mean()) * 100, 2),
        "buy_count": len(buys),
        "hold_count": len(holds),
        "buy_accuracy": _group_accuracy(buys),
        "hold_accuracy": _group_accuracy(holds),
        "avg_forward_return": round(float(forward.mean()) * 100, 3),
        "avg_active_return": None if len(active) == 0 else round(float(active.mean()) * 100, 3),
        "avg_decision_edge": round(float(edge.mean()) * 100, 3),
        "decision_edge_ci_95": [
            round(edge_ci["lower"] * 100, 3),
            round(edge_ci["upper"] * 100, 3),
        ],
        "decision_edge_p_value": round(edge_test["p_value"], 4),
        "decision_edge_z": round(edge_test["z"], 3),
        "median_forward_return": round(float(np.median(forward)) * 100, 3),
        "calibration": _calibration_bins(decisions),
    }


def _decision_confidence(strategy: str, history: np.ndarray, decision: str) -> float:
    if len(history) < 2:
        return 0.5
    name = strategy.lower().replace("-", "_")
    returns = np.diff(history) / history[:-1]
    realized_vol = float(np.std(returns[-63:])) if len(returns) >= 2 else 0.0
    realized_vol = max(realized_vol, 1e-6)

    if name in {"momentum", "trend"} and len(history) > 63:
        strength = abs(history[-1] / history[-64] - 1) / (realized_vol * np.sqrt(63))
    elif name in {"agent", "sma", "sma_cross"} and len(history) >= 50:
        fast = history[-20:].mean()
        slow = history[-50:].mean()
        strength = abs(fast / slow - 1) / (realized_vol * np.sqrt(20))
    elif name in {"buy_hold", "buyhold", "hold"}:
        strength = 0.75
    else:
        strength = 0.0

    base = 0.52 if decision == "HOLD" else 0.55
    return float(min(0.95, base + 0.25 * np.tanh(strength)))


def _benchmark_forward_return(benchmark_closes: np.ndarray, entry_idx: int, exit_idx: int) -> float | None:
    if len(benchmark_closes) <= exit_idx:
        return None
    return float(benchmark_closes[exit_idx] / benchmark_closes[entry_idx] - 1)


def _decision_correct(decision: str, score_return: float, neutral_band: float) -> bool:
    if decision == "BUY":
        return score_return > neutral_band
    if decision == "SELL":
        return score_return < -neutral_band
    return score_return <= neutral_band


def _group_accuracy(decisions: Sequence[HistoricalDecision]) -> float | None:
    if not decisions:
        return None
    return round(100 * sum(d.correct for d in decisions) / len(decisions), 2)


def _calibration_bins(decisions: Sequence[HistoricalDecision]) -> List[Dict]:
    bins = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    result = []
    for low, high in bins:
        bucket = [d for d in decisions if low <= d.confidence < high]
        if not bucket:
            continue
        result.append({
            "bin": f"{low:.1f}-{min(high, 1.0):.1f}",
            "n": len(bucket),
            "avg_confidence": round(100 * sum(d.confidence for d in bucket) / len(bucket), 2),
            "accuracy": _group_accuracy(bucket),
        })
    return result
