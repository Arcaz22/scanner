from datetime import datetime

from app.core.settings import Settings, get_settings
from app.domain.bandarmology import BrokerSummaryData
from app.domain.enums import RiskLevel, Sentiment, SignalStatus
from app.domain.fundamental import FundamentalData
from app.domain.market import PriceData
from app.domain.news import NewsResult
from app.domain.signal import SignalFlag


class SignalService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def evaluate(
        self,
        price: PriceData | None = None,
        fundamental: FundamentalData | None = None,
        news: NewsResult | None = None,
        broker: BrokerSummaryData | None = None,
    ) -> SignalFlag:
        volume_spike = bool(price and price.volume_ratio >= self.settings.volume_spike_multiplier)
        price_movement = bool(price and abs(price.price_change_pct) >= self.settings.price_change_threshold)
        near_resistance = bool(price and price.close >= price.high_30d * 0.98)
        near_support = bool(price and price.close <= price.low_30d * 1.02)
        foreign_interest = bool(news and news.has_foreign_interest)
        big_accumulation = bool(broker and broker.is_big_accumulation)
        foreign_net_buy = bool(broker and broker.has_foreign_net_buy)
        positive_news = bool(news and news.overall_sentiment == Sentiment.POSITIVE)

        triggers_count = sum(
            [
                volume_spike,
                price_movement,
                near_resistance,
                near_support,
                foreign_interest,
                big_accumulation,
                foreign_net_buy,
                positive_news,
            ]
        )

        risk_level = fundamental.risk_level if fundamental else RiskLevel.UNKNOWN
        if triggers_count == 0:
            status = SignalStatus.NORMAL
        elif risk_level == RiskLevel.HIGH:
            status = SignalStatus.CAUTION
        else:
            status = SignalStatus.SIGNAL

        notes = self._notes(
            volume_spike,
            price_movement,
            near_resistance,
            near_support,
            foreign_interest,
            big_accumulation,
            foreign_net_buy,
            positive_news,
            risk_level,
        )

        signal_date = price.date if price else datetime.combine(broker.date, datetime.min.time()) if broker else fundamental.fetched_at if fundamental else datetime.now()

        return SignalFlag(
            ticker=(price.ticker if price else broker.ticker if broker else fundamental.ticker if fundamental else ""),
            date=signal_date,
            status=status,
            volume_spike=volume_spike,
            price_movement=price_movement,
            near_resistance=near_resistance,
            near_support=near_support,
            foreign_interest=foreign_interest,
            big_accumulation=big_accumulation,
            foreign_net_buy=foreign_net_buy,
            positive_news=positive_news,
            triggers_count=triggers_count,
            notes=", ".join(notes),
        )

    def _notes(self, *flags) -> list[str]:
        labels = [
            "volume spike",
            "price movement",
            "near resistance",
            "near support",
            "news foreign interest",
            "big accumulation",
            "foreign net buy",
            "positive news",
        ]
        notes = [label for flag, label in zip(flags[:8], labels, strict=True) if flag]
        risk_level = flags[8]
        if risk_level == RiskLevel.HIGH:
            notes.append("high risk fundamental")
        return notes
