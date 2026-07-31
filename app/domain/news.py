from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.enums import Sentiment


@dataclass
class NewsItem:
    """Satu item berita."""

    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None
    sentiment: Sentiment = Sentiment.NEUTRAL


@dataclass
class NewsResult:
    """Hasil pencarian berita untuk satu saham."""

    ticker: str
    items: list[NewsItem] = field(default_factory=list)
    overall_sentiment: Sentiment = Sentiment.NEUTRAL
    has_foreign_interest: bool = False
    searched_at: datetime = field(default_factory=datetime.now)
