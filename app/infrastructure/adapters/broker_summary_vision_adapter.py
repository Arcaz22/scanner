import base64
import re
from datetime import date
from pathlib import Path
from typing import Any

import requests

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.domain.bandarmology import BrokerSummaryData
from app.utils.helper import normalize_ticker

logger = get_logger(__name__)


class BrokerSummaryVisionAdapter:
    """
    Parse screenshot broker summary dengan Ollama vision model.

    Model diminta mengembalikan JSON array agar hasilnya bisa langsung masuk DB.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def load(
        self,
        source: str | Path,
        source_file: str | None = None,
        ticker_hint: str | None = None,
    ) -> list[BrokerSummaryData]:
        path = Path(source)
        logger.info("Vision parse start file=%s ticker_hint=%s model=%s", source_file or path.name, ticker_hint or "-", self.settings.ollama_vision_model)
        ticker = normalize_ticker(ticker_hint) if ticker_hint else self._read_ticker(path, source_file or path.name)
        buy_text = self._ask_values(path, "B.val")
        sell_text = self._ask_values(path, "S.val")
        buy_values = self._money_tokens(buy_text)
        sell_values = self._money_tokens(sell_text)
        close = self._read_close(path)

        logger.info("Vision columns parsed ticker=%s buy_count=%s sell_count=%s", ticker or "-", len(buy_values), len(sell_values))

        if not ticker:
            raise ValueError(
                "Broker summary tidak terbaca. Jika screenshot tidak menampilkan ticker, gunakan format `/broker GMFI`."
            )
        if not buy_values or not sell_values:
            raise ValueError(
                "Kolom B.val/S.val tidak terbaca. Crop screenshot ke tabel broker summary, "
                "atau gunakan `/broker GMFI` dengan CSV untuk hasil paling akurat."
            )

        parsed = [
            BrokerSummaryData(
                ticker=ticker,
                date=date.today(),
                top3_buy_val=self._top_sum(buy_values, 3),
                top3_sell_val=self._top_sum(sell_values, 3),
                net_foreign_val=0.0,
                total_buy_val=sum(buy_values),
                total_sell_val=sum(sell_values),
                close=close,
                source_file=source_file or path.name,
            )
        ]
        logger.info(
            "Vision parse success file=%s ticker=%s top3_buy=%s top3_sell=%s total_buy=%s total_sell=%s close=%s",
            source_file or path.name,
            ticker,
            parsed[0].top3_buy_val,
            parsed[0].top3_sell_val,
            parsed[0].total_buy_val,
            parsed[0].total_sell_val,
            close,
        )
        return parsed

    def _ask_values(self, path: Path, column_name: str) -> str:
        column_hint = ""
        if column_name == "B.val":
            column_hint = (
                "B.val is the green money column immediately after BY. "
                "Do not read B.lot. Example: in row BR, B.val is 1B and B.lot is 188.5K; answer 1B, not 188.5K. "
            )
        elif column_name == "S.val":
            column_hint = (
                "S.val is the red money column immediately after SL. "
                "Do not read S.lot. Example: in row BQ, S.val is 1.8B and S.lot is 329.1K; answer 1.8B, not 329.1K. "
            )
        prompt = (
            f"Read ONLY the {column_name} column from this Stockbit broker summary table. "
            f"{column_hint}"
            "Return only visible money values from top to bottom, comma separated. "
            "Keep suffix B, M, or K exactly. Do not read lot/freq/avg columns. "
            "Example answer: 1B,762M,370.1M,351.4M. "
            "No JSON. No explanation."
        )
        fallback_prompt = (
            f"What are the visible values under column {column_name}? "
            "Answer only comma-separated values with B, M, or K suffix."
        )
        return self._ask_ollama_text(path, prompt, label=column_name, fallback_prompt=fallback_prompt)

    def _read_ticker(self, path: Path, source_file: str) -> str:
        file_ticker = self._extract_ticker(source_file)
        if file_ticker:
            return file_ticker
        prompt = (
            "Read the stock ticker code in the top header. "
            "Return only one 4 or 5 letter IDX ticker, for example GMFI. "
            "If there is no ticker, return NONE."
        )
        text = self._ask_ollama_text(path, prompt, label="ticker", required=False)
        ticker = self._extract_ticker(text)
        logger.info("Vision ticker parsed=%s", ticker or "-")
        return ticker

    def _read_close(self, path: Path) -> float | None:
        prompt = (
            "Read the last stock price in the top header near the ticker. "
            "Return only the number, for example 54. If not visible, return NONE."
        )
        text = self._ask_ollama_text(path, prompt, label="close", required=False)
        if re.search(r"\d\s*[BMK]\b", text.upper()):
            logger.info("Vision close ignored because response looks like volume/lot value")
            return None
        close = self._optional_number(text)
        logger.info("Vision close parsed=%s", close if close is not None else "-")
        return close

    def _ask_ollama_text(
        self,
        path: Path,
        prompt: str,
        label: str,
        fallback_prompt: str | None = None,
        required: bool = True,
    ) -> str:
        text = self._request_ollama_text(path, prompt, label)
        if text:
            return text
        if fallback_prompt:
            logger.warning("Ollama vision empty response label=%s; retrying with fallback prompt", label)
            text = self._request_ollama_text(path, fallback_prompt, f"{label}_fallback")
            if text:
                return text
        if not required:
            logger.warning("Ollama vision optional label=%s returned empty; continuing", label)
            return ""
        raise ValueError(
            f"Ollama vision model `{self.settings.ollama_vision_model}` tidak mengembalikan hasil untuk `{label}`. "
            "Pastikan model vision aktif, screenshot jelas/crop ke tabel, dan gunakan `/broker GMFI` jika ticker tidak terlihat."
        )

    def _request_ollama_text(self, path: Path, prompt: str, label: str) -> str:
        image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/generate"
        try:
            response = requests.post(
                url,
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
        except requests.RequestException as err:
            logger.exception("Ollama vision request failed")
            response = getattr(err, "response", None)
            body = response.text[:500] if response is not None else ""
            if response is not None and response.status_code == 404:
                raise ValueError(
                    "Ollama vision endpoint/model tidak ditemukan. "
                    f"Cek OLLAMA_BASE_URL={self.settings.ollama_base_url} dan "
                    f"OLLAMA_VISION_MODEL={self.settings.ollama_vision_model}. "
                    f"Response: {body}"
                ) from err
            raise ValueError(f"Ollama vision gagal dihubungi: {err}. Response: {body}") from err
        text = (response.json().get("response") or "").strip()
        if not text:
            logger.warning("Ollama vision empty response label=%s body_preview=%r", label, response.text[:500])
        return text

    def _ticker(self, row: dict[str, Any], ticker_hint: str | None, source_file: str) -> str:
        for value in (row.get("ticker"), ticker_hint, source_file):
            ticker = self._extract_ticker(value)
            if ticker:
                return ticker
        return ""

    def _extract_ticker(self, value: Any) -> str:
        if not value:
            return ""
        for token in re.findall(r"\b[A-Za-z]{4,5}\b", str(value).upper()):
            if token not in {"JPEG", "JPG", "PNG", "WEBP"}:
                return normalize_ticker(token)
        return ""

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

    def _money_number(self, value: Any) -> float:
        parsed = self._optional_money_number(value)
        return parsed if parsed is not None else 0.0

    def _money_list(self, row: dict[str, Any], *keys: str) -> list[float]:
        values: Any = None
        for key in keys:
            if key in row:
                values = row[key]
                break
        if values is None:
            return []
        if isinstance(values, str):
            values = re.split(r"[,;\n]+", values)
        if not isinstance(values, list):
            return []
        return [parsed for item in values if (parsed := self._optional_money_number(item)) is not None]

    def _money_tokens(self, text: str) -> list[float]:
        tokens = re.findall(r"\b\d+(?:[.,]\d+)?\s*[BMK]\b", text.upper())
        return [parsed for token in tokens if (parsed := self._optional_money_number(token)) is not None]

    def _top_sum(self, values: list[float], count: int) -> float:
        return sum(sorted(values, reverse=True)[:count])

    def _optional_money_number(self, value: Any) -> float | None:
        return self._optional_number(value, assume_million_for_small=True)

    def _optional_number(self, value: Any, assume_million_for_small: bool = False) -> float | None:
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
        elif "." in text:
            before, after = text.split(".", 1)
            if len(after) == 3 and len(before) <= 3:
                text = before + after
        if not text or text in {"-", "."}:
            return None
        value = float(text) * multiplier
        if assume_million_for_small and multiplier == 1.0 and 0 < value < 1_000_000:
            return value * 1_000_000
        return value
