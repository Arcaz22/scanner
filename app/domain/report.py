from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import SignalStatus
from app.domain.bandarmology import BrokerSummaryData
from app.domain.fundamental import FundamentalData
from app.domain.market import PriceData
from app.domain.news import NewsResult
from app.domain.signal import SignalFlag


@dataclass
class DailyReport:
    """Laporan harian lengkap."""

    date: datetime
    signals: list[SignalFlag] = field(default_factory=list)
    price_data: dict[str, PriceData] = field(default_factory=dict)
    broker_data: dict[str, BrokerSummaryData] = field(default_factory=dict)
    news_data: dict[str, NewsResult] = field(default_factory=dict)
    fundamental_data: dict[str, FundamentalData] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)

    def get_signals(self) -> list[SignalFlag]:
        return [s for s in self.signals if s.status == SignalStatus.SIGNAL]

    def get_cautions(self) -> list[SignalFlag]:
        return [s for s in self.signals if s.status == SignalStatus.CAUTION]

    def get_normals(self) -> list[SignalFlag]:
        return [s for s in self.signals if s.status == SignalStatus.NORMAL]
