from app.domain.enums import RiskLevel
from app.domain.saham import SahamInfo
from app.utils.helper import load_watchlist


class WatchlistService:
    def list_saham(self) -> list[SahamInfo]:
        saham = []
        for item in load_watchlist():
            saham.append(
                SahamInfo(
                    ticker=item["ticker"],
                    nama=item.get("nama", ""),
                    risk_level=RiskLevel(item.get("risk_level", RiskLevel.UNKNOWN.value)),
                    catatan=item.get("catatan", ""),
                )
            )
        return saham

    def list_tickers(self) -> list[str]:
        return [item.ticker for item in self.list_saham()]
