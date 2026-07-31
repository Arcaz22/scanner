from dataclasses import dataclass
from datetime import datetime


@dataclass
class PriceData:
    """Data harga dan volume harian."""

    ticker: str
    date: datetime
    close: float
    volume: int
    volume_avg_20d: float
    price_change_pct: float
    high_30d: float
    low_30d: float

    @property
    def volume_ratio(self) -> float:
        if self.volume_avg_20d == 0:
            return 0.0
        return self.volume / self.volume_avg_20d

    @property
    def resistance(self) -> float:
        return self.high_30d

    @property
    def support(self) -> float:
        return self.low_30d
