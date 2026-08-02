from datetime import datetime
from pathlib import Path
import re

from app.core.logging import get_logger
from app.domain.bandarmology import BrokerSummaryData
from app.domain.fundamental import FundamentalData
from app.domain.news import NewsResult
from app.domain.notification import NotificationResult
from app.domain.ports import BrokerSummaryProvider, NewsProvider, ReportNotifier
from app.domain.report import DailyReport
from app.infrastructure.adapters.broker_summary_csv_adapter import BrokerSummaryCSVAdapter
from app.infrastructure.adapters.broker_summary_vision_adapter import BrokerSummaryVisionAdapter
from app.infrastructure.adapters.idx_fundamental_adapter import IDXFinancialRatioAdapter
from app.infrastructure.adapters.tavily_adapter import TavilyAdapter
from app.infrastructure.db.repositories.broker_summary_repository import BrokerSummaryRepository
from app.infrastructure.db.repositories.fundamental_repository import FundamentalRepository
from app.infrastructure.db.repositories.scan_repository import ScanRepository
from app.infrastructure.db.session import get_session_factory
from app.services.signal_service import SignalService

logger = get_logger(__name__)


class ScannerService:
    def __init__(
        self,
        broker_summary: BrokerSummaryProvider | None = None,
        news_provider: NewsProvider | None = None,
        notifier: ReportNotifier | None = None,
        signal_service: SignalService | None = None,
    ):
        self.broker_summary = broker_summary
        self.news_provider = news_provider
        self.notifier = notifier
        self.signal_service = signal_service or SignalService()

    async def update_fundamental_statement_file(
        self,
        source: str | Path,
        ticker: str | None = None,
        source_file: str | None = None,
    ) -> FundamentalData:
        path = Path(source)
        ticker = ticker or self._ticker_from_financial_statement_filename(path.name)
        if not ticker:
            raise ValueError(
                "Ticker tidak ditemukan dari nama file. Gunakan format FinancialStatement-YYYY-PERIOD-TICKER.xlsx"
            )

        adapter = IDXFinancialRatioAdapter()
        data = adapter._parse_financial_statement_xlsx(path, ticker)
        data.source_file = source_file or path.name
        company_name = adapter.find_financial_statement_company_name(path)

        async with get_session_factory()() as db:
            repository = FundamentalRepository(db)
            await repository.upsert(data, nama=company_name or "")
            await db.commit()

        logger.info("Fundamental statement updated: %s", data.ticker)
        return data

    def _annualized_eps(self, eps: float | None, fs_date: datetime | None) -> float | None:
        if eps is None:
            return None
        if fs_date is None or fs_date.month <= 0:
            return eps
        return eps * (12 / fs_date.month)

    def _ticker_from_financial_statement_filename(self, filename: str) -> str | None:
        match = re.search(
            r"(?:^|_)FinancialStatement-\d{4}-[^-]+-([A-Za-z0-9]{4,5})\.(?:xlsx|xls)$",
            Path(filename).name,
            re.IGNORECASE,
        )
        return match.group(1).upper() if match else None

    async def update_broker_summary(self, source: str | Path, source_file: str | None = None) -> list[BrokerSummaryData]:
        adapter = BrokerSummaryCSVAdapter()
        rows = adapter.load(source, source_file=source_file)
        updated: list[BrokerSummaryData] = []

        async with get_session_factory()() as db:
            repository = BrokerSummaryRepository(db)
            for data in rows:
                await repository.upsert(data)
                updated.append(data)
            await db.commit()

        logger.info("Broker summary updated: %s saham", len(updated))
        return updated

    async def update_broker_summary_screenshot(
        self,
        source: str | Path,
        source_file: str | None = None,
        ticker_hint: str | None = None,
    ) -> list[BrokerSummaryData]:
        adapter = BrokerSummaryVisionAdapter()
        rows = adapter.load(source, source_file=source_file, ticker_hint=ticker_hint)
        updated: list[BrokerSummaryData] = []

        async with get_session_factory()() as db:
            repository = BrokerSummaryRepository(db)
            for data in rows:
                await repository.upsert(data)
                updated.append(data)
            await db.commit()

        logger.info("Broker summary screenshot updated: %s saham", len(updated))
        return updated

    async def run_daily_scan(self, include_news: bool = True) -> DailyReport:
        report = DailyReport(date=datetime.now())

        news_provider = self.news_provider
        if include_news and news_provider is None:
            news_provider = TavilyAdapter()

        async with get_session_factory()() as db:
            fundamental_repository = FundamentalRepository(db)
            broker_repository = self.broker_summary or BrokerSummaryRepository(db)
            scan_repository = ScanRepository(db)
            latest_brokers = await broker_repository.get_latest_per_ticker()

            for broker in latest_brokers:
                fundamental = await fundamental_repository.get(broker.ticker)
                signal = self.signal_service.evaluate(None, fundamental, None, broker)
                news = None

                if include_news and self._should_fetch_news(signal, fundamental, broker):
                    company_name = fundamental.nama if fundamental else ""
                    news = await self._get_news(broker.ticker, company_name, scan_repository, news_provider)
                    signal = self.signal_service.evaluate(None, fundamental, news, broker)

                scan_repository.save_scan(None, signal)
                report.broker_data[broker.ticker] = broker
                if fundamental:
                    report.fundamental_data[broker.ticker] = fundamental
                if news:
                    report.news_data[broker.ticker] = news
                report.signals.append(signal)

            await db.commit()

        logger.info("Daily scan complete: %s saham", len(report.signals))
        return report

    def send_daily_report(self, report: DailyReport) -> NotificationResult:
        if self.notifier is None:
            from app.infrastructure.adapters.discord_adapter import DiscordAdapter

            self.notifier = DiscordAdapter()
        return self.notifier.send_daily_report(report)

    async def _get_news(
        self,
        ticker: str,
        nama: str,
        repository: ScanRepository,
        news_provider: NewsProvider | None,
    ) -> NewsResult | None:
        if news_provider is None:
            return None

        cached = await repository.get_news_today(ticker)
        if cached:
            return cached

        news = news_provider.search_news(ticker, nama)
        if news:
            repository.save_news(news)
        return news

    def _should_fetch_news(
        self,
        signal,
        fundamental: FundamentalData | None,
        broker: BrokerSummaryData | None = None,
    ) -> bool:
        if signal.triggers_count == 0 or fundamental is None:
            return False
        per_ok = fundamental.per is None or fundamental.per < 15
        roe_ok = fundamental.roe is None or fundamental.roe > 10
        high_risk = fundamental.risk_level.value == "high"
        broker_ok = broker is None or broker.is_bandarmology_signal
        return per_ok and roe_ok and not high_risk and broker_ok
