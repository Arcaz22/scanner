from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, Float, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SahamFundamental(Base):
    """
    Tabel: saham_fundamental
    Update: 1x seminggu (Sabtu)
    Isi: DER, PER, Cash Flow per saham
    """
    __tablename__ = "saham_fundamental"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    nama: Mapped[str] = mapped_column(String(100), default="")

    # Nullable fields menggunakan Optional
    der: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    per: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pbv: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    npm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    eps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cf_positive: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    cf_neg_quarters: Mapped[int] = mapped_column(Integer, default=0)
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")

    # JSON fields dengan type hinting list/dict
    red_flags: Mapped[list[str]] = mapped_column(JSON, default=list)

    catatan: Mapped[str] = mapped_column(Text, default="")
    fs_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_file: Mapped[str] = mapped_column(String(255), default="")

    # Timestamps (pastikan menggunakan callable datetime.now, bukan datetime.now())
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<SahamFundamental {self.ticker} | risk={self.risk_level}>"


class DailyScan(Base):
    """
    Tabel: daily_scan
    Update: saat command scan dijalankan.
    Isi: hasil scan per saham dari broker summary terbaru.
    """
    __tablename__ = "daily_scan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    scan_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    close: Mapped[Optional[float]] = mapped_column(Float)
    volume: Mapped[Optional[int]] = mapped_column(Integer)
    volume_avg_20d: Mapped[Optional[float]] = mapped_column(Float)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float)
    price_change_pct: Mapped[Optional[float]] = mapped_column(Float)
    high_30d: Mapped[Optional[float]] = mapped_column(Float)
    low_30d: Mapped[Optional[float]] = mapped_column(Float)

    signal_status: Mapped[Optional[str]] = mapped_column(String(20))

    # JSON dict
    triggers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    triggers_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<DailyScan {self.ticker} {self.scan_date} | {self.signal_status}>"


class BrokerSummary(Base):
    """
    Tabel: broker_summary
    Update: dari upload CSV broker summary / foreign flow.
    """
    __tablename__ = "broker_summary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    summary_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    top3_buy_val: Mapped[float] = mapped_column(Float, nullable=False)
    top3_sell_val: Mapped[float] = mapped_column(Float, nullable=False)
    net_foreign_val: Mapped[float] = mapped_column(Float, default=0.0)
    total_buy_val: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_sell_val: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source_file: Mapped[str] = mapped_column(String(255), default="")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<BrokerSummary {self.ticker} {self.summary_date:%Y-%m-%d}>"


class NewsCache(Base):
    """
    Tabel: news_cache
    Update: on-demand saat ada volume spike
    Isi: berita Tavily per saham per hari (cache supaya tidak re-fetch)
    """
    __tablename__ = "news_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    search_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    overall_sentiment: Mapped[str] = mapped_column(String(20), default="neutral")
    has_foreign_interest: Mapped[bool] = mapped_column(Boolean, default=False)

    # JSON list of dicts
    news_items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    searched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<NewsCache {self.ticker} {self.search_date} | {self.overall_sentiment}>"
