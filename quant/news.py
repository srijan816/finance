"""Point-in-time historical news access."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class NewsItem:
    ticker: str
    published_at: datetime
    headline: str
    source: str = ""
    sentiment: float | None = None
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "published_at": self.published_at.isoformat(),
            "headline": self.headline,
            "source": self.source,
            "sentiment": self.sentiment,
            "url": self.url,
        }


class PointInTimeNewsStore:
    """CSV-backed news store that never returns articles after `as_of`."""

    def __init__(self, items: Iterable[NewsItem]):
        self.items = sorted(items, key=lambda item: item.published_at)

    @classmethod
    def from_csv(cls, path: str | Path) -> "PointInTimeNewsStore":
        items = []
        with open(path, newline="") as handle:
            for row in csv.DictReader(handle):
                published_at = parse_timestamp(row["published_at"])
                sentiment = row.get("sentiment", "")
                items.append(NewsItem(
                    ticker=row["ticker"].upper(),
                    published_at=published_at,
                    headline=row.get("headline", ""),
                    source=row.get("source", ""),
                    sentiment=float(sentiment) if sentiment not in ("", None) else None,
                    url=row.get("url", ""),
                ))
        return cls(items)

    def before(self, ticker: str, as_of: datetime, lookback_days: int | None = None) -> List[NewsItem]:
        ticker = ticker.upper()
        cutoff = as_of
        start = None
        if lookback_days is not None:
            start = cutoff.timestamp() - lookback_days * 24 * 60 * 60
        result = []
        for item in self.items:
            if item.ticker not in {ticker, "MARKET", "*"}:
                continue
            if item.published_at > cutoff:
                break
            if start is not None and item.published_at.timestamp() < start:
                continue
            result.append(item)
        return result

    def sentiment_snapshot(self, ticker: str, as_of: datetime, lookback_days: int = 7) -> dict:
        items = self.before(ticker, as_of, lookback_days)
        scores = [item.sentiment for item in items if item.sentiment is not None]
        return {
            "ticker": ticker.upper(),
            "as_of": as_of.isoformat(),
            "lookback_days": lookback_days,
            "article_count": len(items),
            "avg_sentiment": None if not scores else round(sum(scores) / len(scores), 4),
            "latest_headlines": [item.headline for item in items[-5:]],
        }


def parse_timestamp(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def market_close_utc(date_text: str) -> datetime:
    # Conservative approximation for US equities; production use should consult
    # an exchange calendar and daylight-saving rules.
    date = datetime.fromisoformat(date_text).date()
    return datetime.combine(date, time(hour=21), tzinfo=timezone.utc)


POSITIVE_FINANCE_TERMS = {
    "beat", "beats", "upgrade", "upgraded", "raise", "raised", "growth", "profit", "record",
    "strong", "surge", "surges", "outperform", "buyback", "margin expansion", "positive",
}

NEGATIVE_FINANCE_TERMS = {
    "miss", "misses", "downgrade", "downgraded", "cut", "cuts", "loss", "weak", "lawsuit",
    "probe", "decline", "falls", "plunge", "warning", "negative", "margin pressure",
}


def lexicon_sentiment(text: str) -> float:
    """Timestamp-safe lightweight sentiment for historical text tests."""
    lowered = f" {text.lower()} "
    positive = sum(1 for term in POSITIVE_FINANCE_TERMS if f" {term} " in lowered)
    negative = sum(1 for term in NEGATIVE_FINANCE_TERMS if f" {term} " in lowered)
    total = positive + negative
    if total == 0:
        return 0.0
    return round((positive - negative) / total, 4)
