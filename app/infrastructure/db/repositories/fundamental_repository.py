"""
infrastructure/db/repositories/fundamental_repository.py
---------------------------------------------------------
Query database untuk data fundamental saham.
Satu-satunya tempat yang boleh akses tabel saham_fundamental.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RiskLevel
from app.domain.fundamental import FundamentalData
from app.infrastructure.db.models import SahamFundamental
from app.core.logging import get_logger

logger = get_logger(__name__)


class FundamentalRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, ticker: str) -> Optional[FundamentalData]:
        """Ambil data fundamental satu saham."""
        row = await self.db.get(SahamFundamental, ticker)

        if not row:
            return None

        return self._to_domain(row)

    async def get_all(self) -> list[FundamentalData]:
        """Ambil semua data fundamental."""
        rows = (await self.db.scalars(select(SahamFundamental))).all()
        return [self._to_domain(r) for r in rows]

    async def upsert(self, data: FundamentalData, nama: str = "") -> None:
        """
        Insert atau update data fundamental.
        Kalau sudah ada → update, kalau belum → insert.
        """
        existing = await self.db.get(SahamFundamental, data.ticker)

        if existing:
            existing.nama            = nama or existing.nama
            existing.der             = data.der
            existing.per             = data.per
            existing.pbv             = data.pbv
            existing.roe             = data.roe
            existing.roa             = data.roa
            existing.npm             = data.npm
            existing.eps             = data.eps
            existing.cf_positive     = data.cf_positive
            existing.cf_neg_quarters = data.cf_neg_quarters
            existing.risk_level      = data.risk_level.value
            existing.red_flags       = data.red_flags
            existing.catatan         = data.catatan
            existing.fs_date         = data.fs_date
            existing.source_file     = data.source_file
            existing.fetched_at      = data.fetched_at
            existing.updated_at      = datetime.now()
            logger.info(f"Updated fundamental: {data.ticker}")
        else:
            row = SahamFundamental(
                ticker          = data.ticker,
                nama            = nama,
                der             = data.der,
                per             = data.per,
                pbv             = data.pbv,
                roe             = data.roe,
                roa             = data.roa,
                npm             = data.npm,
                eps             = data.eps,
                cf_positive     = data.cf_positive,
                cf_neg_quarters = data.cf_neg_quarters,
                risk_level      = data.risk_level.value,
                red_flags       = data.red_flags,
                catatan         = data.catatan,
                fs_date         = data.fs_date,
                source_file     = data.source_file,
                fetched_at      = data.fetched_at,
            )
            self.db.add(row)
            logger.info(f"Inserted fundamental: {data.ticker}")

    def _to_domain(self, row: SahamFundamental) -> FundamentalData:
        """Convert ORM row → domain model."""
        return FundamentalData(
            ticker          = row.ticker,
            der             = row.der,
            per             = row.per,
            pbv             = row.pbv,
            roe             = row.roe,
            roa             = row.roa,
            npm             = row.npm,
            eps             = row.eps,
            cf_positive     = row.cf_positive,
            cf_neg_quarters = row.cf_neg_quarters,
            risk_level      = RiskLevel(row.risk_level),
            red_flags       = row.red_flags or [],
            catatan         = row.catatan,
            fs_date         = row.fs_date,
            source_file     = row.source_file,
            fetched_at      = row.fetched_at,
        )
