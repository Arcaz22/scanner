"""
Parser laporan keuangan lokal dari upload Discord.

Adapter ini sengaja hanya membaca file .xlsx/.xls yang sudah tersedia lokal.
Tidak ada fetch otomatis ke IDX atau update fundamental bulanan.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.settings import Settings, get_settings
from app.domain.enums import RiskLevel
from app.domain.fundamental import FundamentalData
from app.utils.helper import normalize_ticker


class IDXFinancialRatioAdapter:
    FINANCIAL_STATEMENT_LABELS = {
        "assets": ("total assets", "jumlah aset", "total aset"),
        "liabilities": ("total liabilities", "jumlah liabilitas", "total liabilitas"),
        "equity": ("total equity", "jumlah ekuitas", "total ekuitas"),
        "revenue": ("sales and revenue", "penjualan dan pendapatan usaha"),
        "profit": (
            "profit (loss) attributable to parent entity",
            "laba (rugi) yang dapat diatribusikan ke entitas induk",
            "profit for the period",
            "profit for the year",
            "laba periode berjalan",
            "laba tahun berjalan",
            "laba bersih",
        ),
        "operating_cash_flow": (
            "total net cash flows received from (used in) operating activities",
            "jumlah arus kas bersih yang diperoleh dari (digunakan untuk) aktivitas operasi",
        ),
        "eps": (
            "basic earnings (loss) per share from continuing operations",
            "laba (rugi) per saham dasar dari operasi yang dilanjutkan",
        ),
    }
    FINANCIAL_STATEMENT_DATE_LABELS = (
        "current period end date",
        "tanggal akhir periode berjalan",
    )
    FINANCIAL_STATEMENT_NAME_LABELS = (
        "entity name",
        "nama entitas",
    )

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _parse_financial_statement_xlsx(self, path: Path, ticker: str) -> FundamentalData:
        sheets = pd.read_excel(path, sheet_name=None, header=None)
        values: dict[str, float] = {}
        for df in sheets.values():
            for key, labels in self.FINANCIAL_STATEMENT_LABELS.items():
                if key in values:
                    continue
                found = self._find_statement_value(df, labels)
                if found is not None:
                    values[key] = found

        assets = values.get("assets")
        liabilities = values.get("liabilities")
        equity = values.get("equity")
        revenue = values.get("revenue")
        profit = values.get("profit")
        operating_cash_flow = values.get("operating_cash_flow")
        data = FundamentalData(
            ticker=normalize_ticker(ticker),
            der=(liabilities / equity) if liabilities is not None and equity else None,
            roe=(profit / equity * 100) if profit is not None and equity else None,
            roa=(profit / assets * 100) if profit is not None and assets else None,
            npm=(profit / revenue * 100) if profit is not None and revenue else None,
            eps=values.get("eps"),
            cf_positive=operating_cash_flow > 0 if operating_cash_flow is not None else None,
            fs_date=self._find_statement_date(sheets),
            risk_level=RiskLevel.LOW,
            fetched_at=datetime.now(),
        )
        data.catatan = self._statement_note(values)
        data.risk_level, data.red_flags = self._evaluate(data)
        return data

    def find_financial_statement_company_name(self, path: Path) -> str:
        sheets = pd.read_excel(path, sheet_name=None, header=None)
        for df in sheets.values():
            for _, row in df.iterrows():
                cells = row.tolist()
                normalized_cells = [self._clean_text(cell) for cell in cells]
                if not any(
                    any(label == cell for label in self.FINANCIAL_STATEMENT_NAME_LABELS)
                    for cell in normalized_cells
                ):
                    continue
                for value in cells[1:]:
                    if pd.isna(value):
                        continue
                    text = str(value).strip()
                    if text and self._clean_text(text) not in self.FINANCIAL_STATEMENT_NAME_LABELS:
                        return text
        return ""

    def _find_statement_value(self, df: pd.DataFrame, labels: tuple[str, ...]) -> float | None:
        for _, row in df.iterrows():
            cells = row.tolist()
            normalized_cells = [self._clean_text(cell) for cell in cells]
            if not any(any(label == cell for label in labels) for cell in normalized_cells):
                continue
            for value in cells[1:]:
                number = self._scalar_number(value)
                if number is not None:
                    return number
        return None

    def _find_statement_date(self, sheets: dict[str, pd.DataFrame]) -> datetime | None:
        for df in sheets.values():
            for _, row in df.iterrows():
                cells = row.tolist()
                normalized_cells = [self._clean_text(cell) for cell in cells]
                if not any(
                    any(label == cell for label in self.FINANCIAL_STATEMENT_DATE_LABELS)
                    for cell in normalized_cells
                ):
                    continue
                for value in cells[1:]:
                    if pd.isna(value):
                        continue
                    parsed = pd.to_datetime(value, errors="coerce")
                    if not pd.isna(parsed):
                        return parsed.to_pydatetime()
        return None

    def _statement_note(self, values: dict[str, float]) -> str:
        parts = []
        if "operating_cash_flow" in values:
            parts.append(f"operating_cash_flow={values['operating_cash_flow']:.0f}")
        if "revenue" in values:
            parts.append(f"revenue={values['revenue']:.0f}")
        if "profit" in values:
            parts.append(f"profit={values['profit']:.0f}")
        return "; ".join(parts)

    def _evaluate(self, data: FundamentalData) -> tuple[RiskLevel, list[str]]:
        red_flags = []
        score = 0
        if data.der is not None and data.der > self.settings.der_danger:
            red_flags.append(f"DER {data.der:.2f}x")
            score += 2
        elif data.der is not None and data.der > self.settings.der_caution:
            red_flags.append(f"DER {data.der:.2f}x")
            score += 1
        if data.per is not None and data.per > self.settings.per_very_high:
            red_flags.append(f"PER {data.per:.1f}x")
            score += 2
        elif data.per is not None and data.per > self.settings.per_high:
            red_flags.append(f"PER {data.per:.1f}x")
            score += 1
        if data.roe is not None and data.roe < 0:
            red_flags.append(f"ROE {data.roe:.1f}%")
            score += 1
        if score >= 3:
            return RiskLevel.HIGH, red_flags
        if score >= 1:
            return RiskLevel.MEDIUM, red_flags
        return RiskLevel.LOW, red_flags

    def _scalar_number(self, value: Any) -> float | None:
        if pd.isna(value) or value == "-":
            return None
        if isinstance(value, str):
            value = self._parse_number_text(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _parse_number_text(self, value: str) -> str:
        cleaned = re.sub(r"[xX% ]", "", value.strip())
        if "," in cleaned and "." in cleaned:
            return cleaned.replace(".", "").replace(",", ".")
        if "," in cleaned:
            return cleaned.replace(",", ".")
        return cleaned

    def _clean_text(self, value: Any) -> str:
        return " ".join(str(value).strip().lower().split())
