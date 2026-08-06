from dataclasses import dataclass

from app.domain.enums import RiskLevel


@dataclass
class SahamInfo:
    """Info dasar saham."""

    ticker: str
    nama: str
    risk_level: RiskLevel
    catatan: str = ""
