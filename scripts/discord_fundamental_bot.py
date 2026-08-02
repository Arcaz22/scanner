"""
Discord bot untuk update fundamental, broker summary, scan, dan tanya data DB.

Usage:
  python scripts/discord_fundamental_bot.py

Kirim pesan di channel CH_BOT:
  /help

Bot berjalan sebagai poller sehingga cocok untuk deploy sederhana tanpa public webhook.
"""

import asyncio
import os
import re
import sys
from pathlib import Path
from tempfile import gettempdir
from typing import Any

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import setup_logging
from app.core.settings import get_settings
from app.services.ask_service import AskService
from app.services.scanner_service import ScannerService


logger = setup_logging()


class DiscordFundamentalBot:
    API_BASE = "https://discord.com/api/v10"
    ALLOWED_EXCEL_SUFFIXES = {".xlsx", ".xls"}
    ALLOWED_CSV_SUFFIXES = {".csv"}
    ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.discord_token or not self.settings.ch_bot:
            raise ValueError("DISCORD_TOKEN dan CH_BOT wajib diisi")

        self.headers = {"Authorization": f"Bot {self.settings.discord_token}"}
        self.bot_user_id = self._get_bot_user_id()
        self.last_message_id: str | None = None
        self.service = ScannerService()
        self.ask_service = AskService()

    def run(self) -> None:
        asyncio.run(self._run_forever())

    async def _run_forever(self) -> None:
        self._skip_existing_messages()
        logger.info("Discord fundamental bot listening on channel %s", self.settings.ch_bot)
        while True:
            try:
                await self._poll_once()
            except Exception as err:
                logger.warning("Discord bot poll failed: %s", err)
            await asyncio.sleep(3)

    async def _poll_once(self) -> None:
        messages = self._fetch_messages()
        for message in reversed(messages):
            self.last_message_id = message["id"]
            raw_content = (message.get("content") or "").strip()
            content = raw_content.lower()
            author = message.get("author") or {}
            if author.get("id") == self.bot_user_id:
                continue

            downloaded_paths: list[Path] = []
            try:
                logger.info("Discord command id=%s content=%r attachments=%s", message["id"], raw_content, len(message.get("attachments", [])))
                broker_like = self._is_broker_command(raw_content, message)
                if content == "/help":
                    await self._send_message(self._help_message())
                elif content == "/add":
                    attachment = self._get_attachment(message, self.ALLOWED_EXCEL_SUFFIXES)
                    downloaded_path = self._download_attachment(attachment, message["id"], self.ALLOWED_EXCEL_SUFFIXES)
                    downloaded_paths.append(downloaded_path)
                    attachment_filename = attachment.get("filename", "")
                    statement_ticker = self.service._ticker_from_financial_statement_filename(
                        attachment_filename
                    )
                    if statement_ticker:
                        data = await self.service.update_fundamental_statement_file(
                            downloaded_path,
                            ticker=statement_ticker,
                            source_file=attachment_filename,
                        )
                        await self._send_message(
                            f"Fundamental statement tersimpan: **{data.ticker}** risk={data.risk_level.value}."
                        )
                    else:
                        raise ValueError(
                            "nama file harus mengandung ticker, contoh FinancialStatement-2026-II-BBCA.xlsx"
                        )
                    self._delete_message(message["id"])
                elif broker_like:
                    manual_data = self._manual_broker_payload(raw_content)
                    if manual_data:
                        data = await self.service.update_broker_summary_values(**manual_data)
                        await self._send_message(
                            f"Broker manual tersimpan: **{data.ticker}** "
                            f"top3_buy={self._format_money(data.top3_buy_val)} "
                            f"top3_sell={self._format_money(data.top3_sell_val)}."
                        )
                        continue
                    attachments = self._get_attachments(
                        message,
                        self.ALLOWED_CSV_SUFFIXES | self.ALLOWED_IMAGE_SUFFIXES,
                    )
                    ticker_hint = self._broker_ticker_hint(raw_content)
                    logger.info("Broker command id=%s attachments=%s ticker_hint=%s", message["id"], len(attachments), ticker_hint or "-")
                    if ticker_hint and len(attachments) > 1:
                        raise ValueError(
                            "untuk banyak gambar, ticker harus terlihat di tiap screenshot. "
                            "Jika screenshot browser tidak ada ticker, kirim satu-satu: `/broker GMFI`."
                        )
                    updated_count = 0
                    for attachment in attachments:
                        downloaded_path = self._download_attachment(
                            attachment,
                            message["id"],
                            self.ALLOWED_CSV_SUFFIXES | self.ALLOWED_IMAGE_SUFFIXES,
                        )
                        downloaded_paths.append(downloaded_path)
                        updated_count += len(
                            await self._process_broker_attachment(attachment, downloaded_path, ticker_hint)
                        )
                    logger.info("Broker command complete id=%s updated_count=%s", message["id"], updated_count)
                    await self._send_message(
                        f"Broker summary tersimpan: {updated_count} saham diupdate."
                    )
                    self._delete_message(message["id"])
                elif content == "/scan":
                    report = await self.service.run_daily_scan(include_news=True)
                    result = self.service.send_daily_report(report)
                    if not result.sent:
                        await self._send_message(f"Scan selesai, tapi report gagal dikirim: {result.message}")
                elif content.startswith("/ask"):
                    question = raw_content[4:].strip()
                    if not question:
                        await self._send_message("Format: `/ask BBCA` atau `/ask top akumulasi`")
                    else:
                        await self._send_message(await self.ask_service.answer(question))
            except ValueError as err:
                logger.exception("Discord command validation failed id=%s content=%r", message.get("id"), raw_content)
                await self._send_message(f"Format command salah: {err}")
            except Exception as err:
                logger.exception("Failed processing Discord command")
                await self._send_message(f"Gagal proses command: {err}")
            finally:
                for downloaded_path in downloaded_paths:
                    if downloaded_path.exists():
                        downloaded_path.unlink()
                        logger.debug("Deleted uploaded temp file: %s", downloaded_path)

    def _help_message(self) -> str:
        return (
            "**Perintah Scanner**\n"
            "`/add` + attachment `.xlsx/.xls` - simpan fundamental emiten.\n"
            "`/broker` + attachment `.png/.jpg/.jpeg/.webp` - parse screenshot broker summary pakai moondream.\n"
            "`/broker GMFI` + attachment gambar - pakai GMFI jika ticker tidak terlihat di screenshot.\n"
            "`/broker` + beberapa gambar - bulk jika ticker terlihat di tiap screenshot.\n"
            "`/broker` + attachment `.csv` - import broker summary dari CSV.\n"
            "`/broker GMFI buy=1B,762M sell=1.8B,970M close=54` - input manual jika OCR gagal.\n"
            "`/scan` - scan broker summary terbaru, filter fundamental, cek Tavily bila perlu, lalu kirim report.\n"
            "`/ask rangkum` - ringkasan broker summary terbaru.\n"
            "`/ask BBCA` - detail ticker dan trend akumulasi 5 data terakhir.\n"
            "`/ask top akumulasi` - ranking akumulasi broker.\n"
            "`/ask foreign net buy` - ranking foreign net buy."
        )

    def _broker_ticker_hint(self, content: str) -> str | None:
        parts = content.strip().split(maxsplit=1)
        if len(parts) < 2:
            return None
        match = re.search(r"\b[A-Za-z]{4,5}\b", parts[1].upper())
        return match.group(0) if match else None

    def _is_broker_command(self, content: str, message: dict[str, Any]) -> bool:
        normalized = content.strip().lower()
        return normalized == "/broker" or normalized.startswith("/broker ")

    def _manual_broker_payload(self, content: str) -> dict[str, Any] | None:
        if not re.search(r"\bbuy=", content, re.IGNORECASE) or not re.search(r"\bsell=", content, re.IGNORECASE):
            return None
        ticker = self._broker_ticker_hint(content)
        if not ticker:
            raise ValueError("format manual wajib menyebut ticker, contoh `/broker GMFI buy=1B sell=1.8B`")
        buy_text = self._extract_option(content, "buy")
        sell_text = self._extract_option(content, "sell")
        close_text = self._extract_option(content, "close")
        buy_values = self._money_values(buy_text)
        sell_values = self._money_values(sell_text)
        close = self._number(close_text) if close_text else None
        logger.info("Broker manual parsed ticker=%s buy_count=%s sell_count=%s close=%s", ticker, len(buy_values), len(sell_values), close if close is not None else "-")
        return {
            "ticker": ticker,
            "buy_values": buy_values,
            "sell_values": sell_values,
            "close": close,
        }

    def _extract_option(self, content: str, name: str) -> str:
        match = re.search(rf"\b{name}=([^\s]+)", content, re.IGNORECASE)
        return match.group(1) if match else ""

    def _money_values(self, text: str) -> list[float]:
        return [self._money_value(token) for token in re.findall(r"\d+(?:[.,]\d+)?\s*[BMK]", text.upper())]

    def _money_value(self, token: str) -> float:
        token = token.strip().upper().replace(",", ".")
        multiplier = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000}.get(token[-1], 1)
        return float(token[:-1]) * multiplier

    def _number(self, text: str) -> float | None:
        if not text:
            return None
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None

    def _format_money(self, value: float) -> str:
        if abs(value) >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        return f"{value:,.0f}"

    async def _process_broker_attachment(
        self,
        attachment: dict[str, Any],
        path: Path,
        ticker_hint: str | None,
    ):
        suffix = Path(attachment.get("filename", "")).suffix.lower()
        logger.info(
            "Processing broker attachment file=%s suffix=%s ticker_hint=%s",
            attachment.get("filename", ""),
            suffix,
            ticker_hint or "-",
        )
        if suffix in self.ALLOWED_IMAGE_SUFFIXES:
            return await self.service.update_broker_summary_screenshot(
                path,
                source_file=attachment.get("filename", ""),
                ticker_hint=ticker_hint,
            )
        return await self.service.update_broker_summary(
            path,
            source_file=attachment.get("filename", ""),
        )

    def _skip_existing_messages(self) -> None:
        messages = self._fetch_messages(limit=1)
        if messages:
            self.last_message_id = messages[0]["id"]
            logger.info("Skipping existing Discord messages up to %s", self.last_message_id)

    def _fetch_messages(self, limit: int = 20) -> list[dict[str, Any]]:
        params = {"limit": limit}
        if self.last_message_id:
            params["after"] = self.last_message_id
        response = requests.get(
            f"{self.API_BASE}/channels/{self.settings.ch_bot}/messages",
            headers=self.headers,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        rows = response.json()
        return rows

    def _get_attachment(self, message: dict[str, Any], allowed_suffixes: set[str]) -> dict[str, Any]:
        attachments = self._get_attachments(message, allowed_suffixes)
        if attachments:
            return attachments[0]
        allowed = "/".join(sorted(allowed_suffixes))
        raise ValueError(f"kirim command dengan attachment file {allowed}")

    def _get_attachments(self, message: dict[str, Any], allowed_suffixes: set[str]) -> list[dict[str, Any]]:
        attachments = [
            attachment
            for attachment in message.get("attachments", [])
            if Path(attachment.get("filename", "")).suffix.lower() in allowed_suffixes
        ]
        if attachments:
            return attachments
        allowed = "/".join(sorted(allowed_suffixes))
        raise ValueError(f"kirim command dengan attachment file {allowed}")

    def _download_attachment(self, attachment: dict[str, Any], message_id: str, allowed_suffixes: set[str]) -> Path:
        filename = Path(attachment.get("filename") or "upload").name
        suffix = Path(filename).suffix.lower()
        if suffix not in allowed_suffixes:
            raise ValueError(f"file harus salah satu dari: {', '.join(sorted(allowed_suffixes))}")

        url = attachment.get("url")
        if not url:
            raise ValueError("attachment Discord tidak punya URL download")

        response = requests.get(url, timeout=60)
        response.raise_for_status()

        target_dir = Path(gettempdir()) / "scanner_discord_uploads"
        target_dir.mkdir(parents=True, exist_ok=True)
        output = target_dir / f"{message_id}_{filename}"
        output.write_bytes(response.content)
        logger.info("Downloaded Discord attachment file=%s size=%s", filename, len(response.content))
        return output

    async def _send_message(self, content: str) -> None:
        response = requests.post(
            f"{self.API_BASE}/channels/{self.settings.ch_bot}/messages",
            headers={**self.headers, "Content-Type": "application/json"},
            json={"content": content[:1900]},
            timeout=15,
        )
        response.raise_for_status()

    def _delete_message(self, message_id: str) -> None:
        response = requests.delete(
            f"{self.API_BASE}/channels/{self.settings.ch_bot}/messages/{message_id}",
            headers=self.headers,
            timeout=15,
        )
        if response.status_code >= 400:
            logger.warning("Gagal hapus pesan command: %s %s", response.status_code, response.text)

    def _get_bot_user_id(self) -> str:
        response = requests.get(f"{self.API_BASE}/users/@me", headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()["id"]


if __name__ == "__main__":
    DiscordFundamentalBot().run()
