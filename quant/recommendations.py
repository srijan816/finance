"""Technical recommendation helpers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntryPlan:
    entry: float
    stop: float
    target: float


def long_entry_plan(
    entry: float,
    atr: float,
    support_stop: float,
    reward_risk: float = 2.0,
    atr_multiple: float = 2.2,
) -> EntryPlan:
    """Build a long trade plan with a stop that is always below the entry."""
    if entry <= 0:
        raise ValueError("entry must be positive")
    if atr <= 0:
        raise ValueError("atr must be positive")
    if reward_risk <= 0:
        raise ValueError("reward_risk must be positive")
    if atr_multiple <= 0:
        raise ValueError("atr_multiple must be positive")

    stop = max(support_stop, entry - atr_multiple * atr)
    if stop >= entry:
        stop = entry - atr_multiple * atr
    target = entry + reward_risk * (entry - stop)
    return EntryPlan(entry=entry, stop=stop, target=target)
