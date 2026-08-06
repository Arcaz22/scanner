import base64
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import requests

from app.core.settings import get_settings
from app.domain.bandarmology import BrokerSummaryData
from app.utils.helper import normalize_ticker


class BrokerSummaryVisionAdapter:
    """
    Parse screenshot broker summary dengan Ollama vision model.

    Model diminta mengembalikan JSON array agar hasilnya bisa langsung masuk DB.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def load(self, source: str | Path, source_file: str | None = None) -> list[BrokerSummaryData]:
        path = Path(source)
        response_text = self._ask_ollama(path)
        payload = self._extract_json(response_text)
        rows = payload if isinstance(payload, list) else payload.get("rows", [])

        parsed: list[BrokerSummaryData] = []
        for row in rows:
            ticker = normalize_ticker(str(row.get("ticker", "")))
            if not ticker:
                continue
            parsed.append(
                BrokerSummaryData(
                    ticker=ticker,
                    date=self._date(row.get("date")),
                    top3_buy_val=self._number(row.get("top3_buy_val")),
                    top3_sell_val=self._number(row.get("top3_sell_val")),
                    net_foreign_val=self._number(row.get("net_foreign_val")),
                    total_buy_val=self._optional_number(row.get("total_buy_val")),
                    total_sell_val=self._optional_number(row.get("total_sell_val")),
                    close=self._optional_number(row.get("close")),
                    source_file=source_file or path.name,
                )
            )
        return parsed

    def _ask_ollama(self, path: Path) -> str:
        image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        prompt = (
            "Baca screenshot broker summary saham Indonesia. "
            "Kembalikan hanya JSON valid berupa array object. "
            "Field wajib: ticker, top3_buy_val, top3_sell_val. "
            "Field opsional: date, net_foreign_val, total_buy_val, total_sell_val, close. "
            "Semua nilai uang harus angka penuh dalam rupiah, tanpa koma, tanpa teks. "
            "Jika ada singkatan B/M, konversi ke angka penuh. "
            "Jangan tambah penjelasan di luar JSON."
        )
        response = requests.post(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/generate",
            json={
                "model": self.settings.ollama_vision_model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=self.settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        text = (response.json().get("response") or "").strip()
        if not text:
            raise ValueError("Ollama vision tidak mengembalikan hasil parser.")
        return text

    def _extract_json(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
            if not match:
                raise ValueError(f"Output moondream bukan JSON: {text[:300]}")
            return json.loads(match.group(1))

    def _date(self, value: Any) -> date:
        if not value:
            return date.today()
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return date.today()

    def _number(self, value: Any) -> float:
        parsed = self._optional_number(value)
        return parsed if parsed is not None else 0.0

    def _optional_number(self, value: Any) -> float | None:
        if value is None:
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

        text = text.replace("Rp", "").replace("rp", "").strip()
        text = re.sub(r"[^0-9,.\-]", "", text)
        if "," in text and "." in text:
            text = text.replace(",", "")
        elif "," in text:
            parts = text.split(",")
            text = ".".join(parts) if len(parts) == 2 and len(parts[1]) <= 2 else "".join(parts)
        elif text.count(".") > 1:
            text = text.replace(".", "")
        elif "." in text:
            before, after = text.split(".", 1)
            if len(after) == 3 and len(before) <= 3:
                text = before + after
        if not text or text in {"-", "."}:
            return None
        return float(text) * multiplier
