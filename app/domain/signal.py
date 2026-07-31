from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import SignalStatus


@dataclass
class SignalFlag:
    """Hasil flagging logic untuk satu saham satu hari."""

    ticker: str
    date: datetime
    status: SignalStatus
    volume_spike: bool = False
    price_movement: bool = False
    near_resistance: bool = False
    near_support: bool = False
    foreign_interest: bool = False
    big_accumulation: bool = False
    foreign_net_buy: bool = False
    positive_news: bool = False
    triggers_count: int = 0
    notes: str = ""
