"""
infrastructure/db/repositories/scan_repository.py
---------------------------------------------------
Query database untuk data scan harian.
Satu-satunya tempat yang boleh akses tabel daily_scan & news_cache.
"""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import Sentiment, SignalStatus
from app.domain.news import NewsItem, NewsResult
from app.domain.signal import SignalFlag
from app.infrastructure.db.models import DailyScan, NewsCache
from app.core.logging import get_logger

logger = get_logger(__name__)


class ScanRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Daily Scan ────────────────────────────────────────────────────────────

    def save_scan(self, price_data, signal: SignalFlag) -> None:
        """Simpan hasil scan harian."""
        row = DailyScan(
            ticker          = signal.ticker,
            scan_date       = signal.date,
            close           = price_data.close if price_data else None,
            volume          = price_data.volume if price_data else None,
            volume_avg_20d  = price_data.volume_avg_20d if price_data else None,
            volume_ratio    = price_data.volume_ratio if price_data else None,
            price_change_pct= price_data.price_change_pct if price_data else None,
            high_30d        = price_data.high_30d if price_data else None,
            low_30d         = price_data.low_30d if price_data else None,
            signal_status   = signal.status.value,
            triggers        = {
                "volume_spike"    : signal.volume_spike,
                "price_movement"  : signal.price_movement,
                "near_resistance" : signal.near_resistance,
                "near_support"    : signal.near_support,
                "foreign_interest": signal.foreign_interest,
                "big_accumulation": signal.big_accumulation,
                "foreign_net_buy" : signal.foreign_net_buy,
                "positive_news"   : signal.positive_news,
            },
            triggers_count  = signal.triggers_count,
            notes           = signal.notes,
        )
        self.db.add(row)
        logger.info(f"Scan saved: {signal.ticker} → {signal.status.value}")

    async def get_latest(self, ticker: str) -> Optional[SignalFlag]:
        """Ambil scan terbaru untuk satu saham."""
        stmt = (
            select(DailyScan)
            .where(DailyScan.ticker == ticker)
            .order_by(DailyScan.scan_date.desc())
            .limit(1)
        )
        row = (await self.db.scalars(stmt)).first()

        return self._scan_to_domain(row) if row else None

    async def get_by_date(self, scan_date: date) -> list[SignalFlag]:
        """Ambil semua scan untuk tanggal tertentu."""
        stmt = select(DailyScan).where(
            DailyScan.scan_date >= datetime.combine(scan_date, datetime.min.time()),
            DailyScan.scan_date < datetime.combine(scan_date, datetime.max.time()),
        )
        rows = (await self.db.scalars(stmt)).all()
        return [self._scan_to_domain(r) for r in rows]

    # ── News Cache ────────────────────────────────────────────────────────────

    def save_news(self, news: NewsResult) -> None:
        """Cache hasil Tavily search."""
        row = NewsCache(
            ticker               = news.ticker,
            search_date          = news.searched_at,
            overall_sentiment    = news.overall_sentiment.value,
            has_foreign_interest = news.has_foreign_interest,
            news_items           = [
                {
                    "title"          : item.title,
                    "url"            : item.url,
                    "snippet"        : item.snippet,
                    "published_date" : item.published_date,
                    "sentiment"      : item.sentiment.value,
                }
                for item in news.items
            ],
        )
        self.db.add(row)
        logger.info(f"News cached: {news.ticker} | {news.overall_sentiment.value}")

    async def get_news_today(self, ticker: str) -> Optional[NewsResult]:
        """Cek apakah sudah ada cache berita hari ini (hindari re-fetch)."""
        today = date.today()
        stmt = (
            select(NewsCache)
            .where(
                NewsCache.ticker == ticker,
                NewsCache.search_date >= datetime.combine(today, datetime.min.time()),
            )
            .limit(1)
        )
        row = (await self.db.scalars(stmt)).first()

        return self._news_to_domain(row) if row else None

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _scan_to_domain(self, row: DailyScan) -> SignalFlag:
        t = row.triggers or {}
        return SignalFlag(
            ticker           = row.ticker,
            date             = row.scan_date,
            status           = SignalStatus(row.signal_status),
            volume_spike     = t.get("volume_spike", False),
            price_movement   = t.get("price_movement", False),
            near_resistance  = t.get("near_resistance", False),
            near_support     = t.get("near_support", False),
            foreign_interest = t.get("foreign_interest", False),
            big_accumulation = t.get("big_accumulation", False),
            foreign_net_buy  = t.get("foreign_net_buy", False),
            positive_news    = t.get("positive_news", False),
            triggers_count   = row.triggers_count,
            notes            = row.notes or "",
        )

    def _news_to_domain(self, row: NewsCache) -> NewsResult:
        items = [
            NewsItem(
                title          = n["title"],
                url            = n["url"],
                snippet        = n["snippet"],
                published_date = n.get("published_date"),
                sentiment      = Sentiment(n.get("sentiment", "neutral")),
            )
            for n in (row.news_items or [])
        ]
        return NewsResult(
            ticker               = row.ticker,
            items                = items,
            overall_sentiment    = Sentiment(row.overall_sentiment),
            has_foreign_interest = row.has_foreign_interest,
            searched_at          = row.searched_at,
        )
