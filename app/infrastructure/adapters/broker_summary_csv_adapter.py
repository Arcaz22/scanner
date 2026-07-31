from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from app.domain.bandarmology import BrokerSummaryData
from app.utils.helper import normalize_ticker


class BrokerSummaryCSVAdapter:
    COLUMN_ALIASES = {
        "ticker": {"ticker", "symbol", "code", "kode", "stock", "saham"},
        "date": {"date", "tanggal", "summary_date"},
        "top3_buy_val": {"top3_buy_val", "top_3_buy_val", "top3buy", "top_buyer_value", "buyer_value", "buy_val", "buy_value"},
        "top3_sell_val": {"top3_sell_val", "top_3_sell_val", "top3sell", "top_seller_value", "seller_value", "sell_val", "sell_value"},
        "net_foreign_val": {"net_foreign_val", "foreign_net", "net_foreign", "foreign_flow", "net_f", "f_net"},
        "total_buy_val": {"total_buy_val", "total_buy", "total_buyer_value"},
        "total_sell_val": {"total_sell_val", "total_sell", "total_seller_value"},
        "close": {"close", "last", "price", "last_price"},
    }

    def load(self, source: str | Path, source_file: str | None = None) -> list[BrokerSummaryData]:
        path = Path(source)
        df = pd.read_csv(path)
        if df.empty:
            return []

        columns = self._map_columns(df.columns)
        self._require(columns, "ticker", "top3_buy_val", "top3_sell_val")

        rows: list[BrokerSummaryData] = []
        for _, row in df.iterrows():
            ticker = normalize_ticker(str(row[columns["ticker"]]))
            if not ticker or ticker.lower() == "nan":
                continue

            summary_date = self._date(row[columns["date"]]) if "date" in columns else date.today()
            rows.append(
                BrokerSummaryData(
                    ticker=ticker,
                    date=summary_date,
                    top3_buy_val=self._number(row[columns["top3_buy_val"]]),
                    top3_sell_val=self._number(row[columns["top3_sell_val"]]),
                    net_foreign_val=self._number(row[columns["net_foreign_val"]]) if "net_foreign_val" in columns else 0.0,
                    total_buy_val=self._optional_number(row[columns["total_buy_val"]]) if "total_buy_val" in columns else None,
                    total_sell_val=self._optional_number(row[columns["total_sell_val"]]) if "total_sell_val" in columns else None,
                    close=self._optional_number(row[columns["close"]]) if "close" in columns else None,
                    source_file=source_file or path.name,
                )
            )
        return rows

    def _map_columns(self, columns: Any) -> dict[str, str]:
        normalized = {self._normalize_column(column): column for column in columns}
        mapped: dict[str, str] = {}
        for target, aliases in self.COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in normalized:
                    mapped[target] = normalized[alias]
                    break
        return mapped

    def _normalize_column(self, value: Any) -> str:
        return str(value).strip().lower().replace(" ", "_").replace("-", "_")

    def _require(self, columns: dict[str, str], *required: str) -> None:
        missing = [name for name in required if name not in columns]
        if missing:
            raise ValueError(f"Kolom broker summary kurang: {', '.join(missing)}")

    def _number(self, value: Any) -> float:
        parsed = self._optional_number(value)
        return parsed if parsed is not None else 0.0

    def _optional_number(self, value: Any) -> float | None:
        if pd.isna(value):
            return None
        text = str(value).strip()
        if not text:
            return None
        text = text.replace(",", "").replace("Rp", "").replace("rp", "").strip()
        if text.endswith("%"):
            text = text[:-1]
        try:
            return float(text)
        except ValueError:
            return None

    def _date(self, value: Any) -> date:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return date.today()
        return parsed.date()
