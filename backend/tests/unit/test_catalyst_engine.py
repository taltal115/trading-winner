from datetime import datetime

from app.engines.catalyst_engine import detect_catalyst
from app.models.entities import NewsItem
from app.models.enums import CatalystType, Sentiment


def _news(headline: str) -> NewsItem:
    return NewsItem(
        id="news_NVDA_2026-07-28_1",
        ticker="NVDA",
        timestamp=datetime(2026, 7, 28, 8, 45, 0),
        headline=headline,
        source="Reuters",
        sentiment=Sentiment.POSITIVE,
        relevance_score=0.9,
    )


def test_detects_announcement_catalyst() -> None:
    result = detect_catalyst([_news("NVIDIA announces new AI chip partnership")])
    assert result.detected
    assert result.catalyst_type == CatalystType.NEWS
    assert "announces" in result.matched_terms


def test_detects_earnings_catalyst() -> None:
    result = detect_catalyst([_news("Company beats expectations and raises guidance")])
    assert result.detected
    assert result.catalyst_type == CatalystType.EARNINGS


def test_no_catalyst_for_plain_headline() -> None:
    result = detect_catalyst([_news("Stock trades in line with the market")])
    assert not result.detected
    assert result.catalyst_type == CatalystType.UNKNOWN
    assert result.matched_terms == []


def test_empty_news_no_catalyst() -> None:
    assert not detect_catalyst([]).detected
