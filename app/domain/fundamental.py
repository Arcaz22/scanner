from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.domain.enums import RiskLevel


@dataclass
class FundamentalData:
    """Data fundamental saham."""

    ticker: str
    der: Optional[float] = None
    per: Optional[float] = None
    pbv: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    npm: Optional[float] = None
    eps: Optional[float] = None
    cf_positive: Optional[bool] = None
    cf_neg_quarters: int = 0
    risk_level: RiskLevel = RiskLevel.UNKNOWN
    red_flags: list[str] = field(default_factory=list)
    catatan: str = ""
    fs_date: Optional[datetime] = None
    source_file: str = ""
    fetched_at: datetime = field(default_factory=datetime.now)
