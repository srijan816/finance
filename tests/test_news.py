"""Tests for quant/news.py"""
from datetime import datetime, timezone

from quant.news import NewsItem, PointInTimeNewsStore


def test_news_store_filters_future_items():
    store = PointInTimeNewsStore([
        NewsItem("AAPL", datetime(2024, 1, 1, tzinfo=timezone.utc), "past", sentiment=0.2),
        NewsItem("AAPL", datetime(2024, 1, 3, tzinfo=timezone.utc), "future", sentiment=-0.5),
    ])
    items = store.before("AAPL", datetime(2024, 1, 2, tzinfo=timezone.utc))
    assert [item.headline for item in items] == ["past"]


def test_sentiment_snapshot_uses_only_prior_news():
    store = PointInTimeNewsStore([
        NewsItem("AAPL", datetime(2024, 1, 1, tzinfo=timezone.utc), "past", sentiment=0.2),
        NewsItem("AAPL", datetime(2024, 1, 3, tzinfo=timezone.utc), "future", sentiment=-0.5),
    ])
    snap = store.sentiment_snapshot("AAPL", datetime(2024, 1, 2, tzinfo=timezone.utc))
    assert snap["article_count"] == 1
    assert snap["avg_sentiment"] == 0.2
