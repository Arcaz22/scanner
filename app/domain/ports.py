from typing import Protocol

from app.domain.bandarmology import BrokerSummaryData
from app.domain.news import NewsResult
from app.domain.notification import NotificationResult
from app.domain.report import DailyReport


class NewsProvider(Protocol):
    def search_news(self, ticker: str, company_name: str = "") -> NewsResult | None:
        ...


class BrokerSummaryProvider(Protocol):
    async def get_latest(self, ticker: str) -> BrokerSummaryData | None:
        ...


class ReportNotifier(Protocol):
    def send_daily_report(self, report: DailyReport) -> NotificationResult:
        ...
