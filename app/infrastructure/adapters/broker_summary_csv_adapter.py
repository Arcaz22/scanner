from datetime import date
from pathlib import Path
import re
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
        "b_val": {"b_val", "b.val", "buy_raw", "buyer_raw"},
        "s_val": {"s_val", "s.val", "sell_raw", "seller_raw"},
    }

    def load(self, source: str | Path, source_file: str | None = None) -> list[BrokerSummaryData]:
        path = Path(source)
        df = pd.read_csv(path)
        if df.empty:
            return []

        columns = self._map_columns(df.columns)
        if "b_val" in columns and "s_val" in columns:
            return self._load_raw_rows(df, columns, source_file or path.name)

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

    def _load_raw_rows(
        self,
        df: pd.DataFrame,
        columns: dict[str, str],
        source_file: str,
    ) -> list[BrokerSummaryData]:
        self._require(columns, "ticker", "b_val", "s_val")

        working = df.copy()
        working["_ticker"] = working[columns["ticker"]].map(lambda value: normalize_ticker(str(value)))
        working = working[working["_ticker"].str.lower() != "nan"]
        working = working[working["_ticker"] != ""]
        if working.empty:
            return []

        if "date" in columns:
            working["_date"] = working[columns["date"]].map(self._date)
        else:
            working["_date"] = date.today()

        rows: list[BrokerSummaryData] = []
        for (ticker, summary_date), group in working.groupby(["_ticker", "_date"], sort=False):
            buy_values = [
                parsed
                for value in group[columns["b_val"]]
                if (parsed := self._optional_money_number(value)) is not None
            ]
            sell_values = [
                parsed
                for value in group[columns["s_val"]]
                if (parsed := self._optional_money_number(value)) is not None
            ]
            if not buy_values or not sell_values:
                continue

            close = None
            if "close" in columns:
                for value in reversed(group[columns["close"]].tolist()):
                    close = self._optional_number(value)
                    if close is not None:
                        break

            rows.append(
                BrokerSummaryData(
                    ticker=ticker,
                    date=summary_date,
                    top3_buy_val=sum(sorted(buy_values, reverse=True)[:3]),
                    top3_sell_val=sum(sorted(sell_values, reverse=True)[:3]),
                    net_foreign_val=self._group_first_number(group, columns, "net_foreign_val", 0.0) or 0.0,
                    total_buy_val=sum(buy_values),
                    total_sell_val=sum(sell_values),
                    close=close,
                    source_file=source_file,
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

    def _optional_money_number(self, value: Any) -> float | None:
        if pd.isna(value):
            return None
        text = str(value).strip()
        if not text:
            return None

        multiplier = 1.0
        suffix = text[-1:].upper()
        if suffix == "B":
            multiplier = 1_000_000_000
            text = text[:-1]
        elif suffix == "M":
            multiplier = 1_000_000
            text = text[:-1]
        elif suffix == "K":
            multiplier = 1_000
            text = text[:-1]

        text = text.replace("Rp", "").replace("rp", "").strip()
        text = re.sub(r"[^0-9,.\-]", "", text)
        if "," in text and "." in text:
            text = text.replace(",", "")
        elif "," in text:
            parts = text.split(",")
            text = ".".join(parts) if len(parts) == 2 and len(parts[1]) <= 2 else "".join(parts)
        elif text.count(".") > 1:
            text = text.replace(".", "")
        if not text or text in {"-", "."}:
            return None
        try:
            return float(text) * multiplier
        except ValueError:
            return None

    def _group_first_number(
        self,
        group: pd.DataFrame,
        columns: dict[str, str],
        key: str,
        default: float | None = None,
    ) -> float | None:
        if key not in columns:
            return default
        for value in group[columns[key]].tolist():
            parsed = self._optional_number(value)
            if parsed is not None:
                return parsed
        return default

    def _date(self, value: Any) -> date:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return date.today()
        return parsed.date()
