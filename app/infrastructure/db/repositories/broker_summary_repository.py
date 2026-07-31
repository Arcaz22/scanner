from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.bandarmology import BrokerSummaryData
from app.infrastructure.db.models import BrokerSummary

logger = get_logger(__name__)


class BrokerSummaryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, data: BrokerSummaryData) -> None:
        start = datetime.combine(data.date, datetime.min.time())
        end = datetime.combine(data.date, datetime.max.time())
        stmt = (
            select(BrokerSummary)
            .where(
                BrokerSummary.ticker == data.ticker,
                BrokerSummary.summary_date >= start,
                BrokerSummary.summary_date <= end,
            )
            .limit(1)
        )
        existing = (await self.db.scalars(stmt)).first()

        if existing:
            existing.top3_buy_val = data.top3_buy_val
            existing.top3_sell_val = data.top3_sell_val
            existing.net_foreign_val = data.net_foreign_val
            existing.total_buy_val = data.total_buy_val
            existing.total_sell_val = data.total_sell_val
            existing.close = data.close
            existing.source_file = data.source_file
            existing.uploaded_at = datetime.now()
            logger.info("Updated broker summary: %s", data.ticker)
            return

        self.db.add(
            BrokerSummary(
                ticker=data.ticker,
                summary_date=datetime.combine(data.date, datetime.min.time()),
                top3_buy_val=data.top3_buy_val,
                top3_sell_val=data.top3_sell_val,
                net_foreign_val=data.net_foreign_val,
                total_buy_val=data.total_buy_val,
                total_sell_val=data.total_sell_val,
                close=data.close,
                source_file=data.source_file,
            )
        )
        logger.info("Inserted broker summary: %s", data.ticker)

    async def get_latest(self, ticker: str) -> BrokerSummaryData | None:
        stmt = (
            select(BrokerSummary)
            .where(BrokerSummary.ticker == ticker.upper())
            .order_by(BrokerSummary.summary_date.desc(), BrokerSummary.uploaded_at.desc())
            .limit(1)
        )
        row = (await self.db.scalars(stmt)).first()
        return self._to_domain(row) if row else None

    async def get_latest_all(self, limit: int = 50) -> list[BrokerSummaryData]:
        stmt = (
            select(BrokerSummary)
            .order_by(BrokerSummary.summary_date.desc(), BrokerSummary.uploaded_at.desc())
            .limit(limit)
        )
        rows = (await self.db.scalars(stmt)).all()
        return [self._to_domain(row) for row in rows]

    async def get_top_accumulation(self, limit: int = 10) -> list[BrokerSummaryData]:
        rows = await self.get_latest_all(limit=500)
        rows.sort(key=lambda item: (item.is_big_accumulation, item.accum_ratio, item.top3_buy_val), reverse=True)
        return rows[:limit]

    async def get_foreign_net_buy(self, limit: int = 10) -> list[BrokerSummaryData]:
        rows = await self.get_latest_all(limit=500)
        rows = [row for row in rows if row.net_foreign_val > 0]
        rows.sort(key=lambda item: item.net_foreign_val, reverse=True)
        return rows[:limit]

    def _to_domain(self, row: BrokerSummary) -> BrokerSummaryData:
        return BrokerSummaryData(
            ticker=row.ticker,
            date=row.summary_date.date(),
            top3_buy_val=row.top3_buy_val,
            top3_sell_val=row.top3_sell_val,
            net_foreign_val=row.net_foreign_val,
            total_buy_val=row.total_buy_val,
            total_sell_val=row.total_sell_val,
            close=row.close,
            source_file=row.source_file,
        )
