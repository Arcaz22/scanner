from datetime import date
from pydantic import BaseModel


class BrokerSummaryData(BaseModel):
    ticker: str
    date: date
    top3_buy_val: float
    top3_sell_val: float
    net_foreign_val: float = 0.0 
    total_buy_val: float | None = None
    total_sell_val: float | None = None
    close: float | None = None
    source_file: str = ""

    @property
    def accum_ratio(self) -> float:
        if self.top3_sell_val == 0:
            return 999.0
        return self.top3_buy_val / self.top3_sell_val

    @property
    def is_big_accumulation(self) -> bool:
        return self.accum_ratio >= 1.3 and self.top3_buy_val >= 1_000_000_000

    @property
    def has_foreign_net_buy(self) -> bool:
        return self.net_foreign_val > 0

    @property
    def is_bandarmology_signal(self) -> bool:
        return self.is_big_accumulation and self.has_foreign_net_buy
