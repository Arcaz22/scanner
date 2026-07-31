import re
import asyncio

import requests

from app.domain.bandarmology import BrokerSummaryData
from app.domain.fundamental import FundamentalData
from app.core.settings import get_settings
from app.infrastructure.db.repositories.broker_summary_repository import BrokerSummaryRepository
from app.infrastructure.db.repositories.fundamental_repository import FundamentalRepository
from app.infrastructure.db.repositories.scan_repository import ScanRepository
from app.infrastructure.db.session import get_session_factory
from app.services.watchlist_service import WatchlistService


class AskService:
    def __init__(self, watchlist_service: WatchlistService | None = None) -> None:
        self.watchlist_service = watchlist_service or WatchlistService()
        self.settings = get_settings()

    async def answer(self, question: str) -> str:
        normalized = question.strip().lower()
        ticker = self._extract_ticker(question)

        async with get_session_factory()() as db:
            broker_repository = BrokerSummaryRepository(db)
            fundamental_repository = FundamentalRepository(db)
            scan_repository = ScanRepository(db)

            if ticker:
                broker = await broker_repository.get_latest(ticker)
                fundamental = await fundamental_repository.get(ticker)
                latest_signal = await scan_repository.get_latest(ticker)
                context = self._ticker_answer(ticker, broker, fundamental, latest_signal)
                return await self._ask_ollama(question, context)

            if any(word in normalized for word in ("foreign", "asing", "net buy")):
                rows = await broker_repository.get_foreign_net_buy(limit=10)
                context = self._broker_list_answer("Top foreign net buy", rows, field="foreign")
                return await self._ask_ollama(question, context)

            if any(word in normalized for word in ("akumulasi", "accum", "bandar", "broker")):
                rows = await broker_repository.get_top_accumulation(limit=10)
                context = self._broker_list_answer("Top akumulasi broker", rows, field="accum")
                return await self._ask_ollama(question, context)

            if any(word in normalized for word in ("signal", "sinyal", "rekomendasi")):
                context = "Data DB belum cukup spesifik. User perlu menyebut ticker atau kategori seperti top akumulasi/foreign net buy."
                return await self._ask_ollama(question, context)

            context = (
                "Saya bisa jawab dari data DB untuk: detail ticker, akumulasi broker, dan foreign net buy. "
                "Contoh: `ask BBCA`, `ask top akumulasi`, `ask foreign net buy`."
            )
            return await self._ask_ollama(question, context)

    async def _ask_ollama(self, question: str, context: str) -> str:
        prompt = (
            "Kamu adalah asisten scanner saham Indonesia. Jawab dalam bahasa Indonesia, singkat, "
            "praktis, dan hanya berdasarkan konteks data yang diberikan. Jika konteks tidak cukup, "
            "katakan data belum cukup dan beri contoh pertanyaan yang bisa dijawab.\n\n"
            f"Konteks data:\n{context}\n\n"
            f"Pertanyaan user:\n{question}\n\n"
            "Jawaban:"
        )
        return await asyncio.to_thread(self._generate_ollama, prompt)

    def _generate_ollama(self, prompt: str) -> str:
        try:
            response = requests.post(
                f"{self.settings.ollama_base_url.rstrip('/')}/api/generate",
                json={
                    "model": self.settings.ollama_text_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                    },
                },
                timeout=self.settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as err:
            return (
                "Ollama tidak bisa dihubungi. "
                f"Cek OLLAMA_BASE_URL={self.settings.ollama_base_url} dan pastikan service Ollama aktif. "
                f"Detail: {err}"
            )[:1900]
        data = response.json()
        answer = (data.get("response") or "").strip()
        if not answer:
            return "Ollama tidak mengembalikan jawaban."
        return answer[:1900]

    def _extract_ticker(self, question: str) -> str | None:
        watchlist = set(self.watchlist_service.list_tickers())
        for token in re.findall(r"\b[A-Za-z]{4,5}\b", question.upper()):
            if token in watchlist:
                return token
        return None

    def _ticker_answer(
        self,
        ticker: str,
        broker: BrokerSummaryData | None,
        fundamental: FundamentalData | None,
        latest_signal,
    ) -> str:
        lines = [f"**{ticker}**"]

        if fundamental:
            lines.append(
                "Fundamental: "
                f"PER={self._fmt(fundamental.per)} ROE={self._fmt(fundamental.roe)} "
                f"DER={self._fmt(fundamental.der)} risk={fundamental.risk_level.value}"
            )
        else:
            lines.append("Fundamental: belum ada data.")

        if broker:
            lines.append(
                "Broker summary: "
                f"tanggal={broker.date} accum={broker.accum_ratio:.2f}x "
                f"top3_buy={self._money(broker.top3_buy_val)} "
                f"top3_sell={self._money(broker.top3_sell_val)} "
                f"foreign_net={self._money(broker.net_foreign_val)}"
            )
            lines.append(
                "Bandarmology: "
                f"big_accumulation={'ya' if broker.is_big_accumulation else 'tidak'}, "
                f"foreign_net_buy={'ya' if broker.has_foreign_net_buy else 'tidak'}"
            )
        else:
            lines.append("Broker summary: belum ada data.")

        if latest_signal:
            lines.append(
                f"Signal terakhir: {latest_signal.status.value}, "
                f"triggers={latest_signal.triggers_count}, notes={latest_signal.notes or '-'}"
            )

        return "\n".join(lines)

    def _broker_list_answer(self, title: str, rows: list[BrokerSummaryData], field: str) -> str:
        if not rows:
            return f"{title}: belum ada data broker summary."

        lines = [f"**{title}**"]
        for row in rows:
            metric = self._money(row.net_foreign_val) if field == "foreign" else f"{row.accum_ratio:.2f}x"
            lines.append(
                f"- {row.ticker} {metric} "
                f"top3_buy={self._money(row.top3_buy_val)} foreign={self._money(row.net_foreign_val)}"
            )
        return "\n".join(lines)

    def _fmt(self, value: float | None) -> str:
        return "-" if value is None else f"{value:.2f}"

    def _money(self, value: float | None) -> str:
        if value is None:
            return "-"
        abs_value = abs(value)
        sign = "-" if value < 0 else ""
        if abs_value >= 1_000_000_000:
            return f"{sign}{abs_value / 1_000_000_000:.2f}B"
        if abs_value >= 1_000_000:
            return f"{sign}{abs_value / 1_000_000:.2f}M"
        return f"{value:,.0f}"
