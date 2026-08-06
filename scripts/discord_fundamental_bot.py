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

            downloaded_path: Path | None = None
            try:
                if content == "/help":
                    await self._send_message(self._help_message())
                elif content == "/add":
                    attachment = self._get_attachment(message, self.ALLOWED_EXCEL_SUFFIXES)
                    downloaded_path = self._download_attachment(attachment, message["id"], self.ALLOWED_EXCEL_SUFFIXES)
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
                elif content == "/broker":
                    attachment = self._get_attachment(
                        message,
                        self.ALLOWED_CSV_SUFFIXES | self.ALLOWED_IMAGE_SUFFIXES,
                    )
                    suffix = Path(attachment.get("filename", "")).suffix.lower()
                    downloaded_path = self._download_attachment(
                        attachment,
                        message["id"],
                        self.ALLOWED_CSV_SUFFIXES | self.ALLOWED_IMAGE_SUFFIXES,
                    )
                    if suffix in self.ALLOWED_IMAGE_SUFFIXES:
                        updated = await self.service.update_broker_summary_screenshot(
                            downloaded_path,
                            source_file=attachment.get("filename", ""),
                        )
                    else:
                        updated = await self.service.update_broker_summary(
                            downloaded_path,
                            source_file=attachment.get("filename", ""),
                        )
                    await self._send_message(
                        f"Broker summary tersimpan: {len(updated)} saham diupdate."
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
                await self._send_message(f"Format command salah: {err}")
            except Exception as err:
                logger.exception("Failed processing Discord command")
                await self._send_message(f"Gagal proses command: {err}")
            finally:
                if downloaded_path and downloaded_path.exists():
                    downloaded_path.unlink()
                    logger.info("Deleted uploaded temp file: %s", downloaded_path)

    def _help_message(self) -> str:
        return (
            "**Perintah Scanner**\n"
            "`/add` + attachment `.xlsx/.xls` - simpan fundamental emiten.\n"
            "`/broker` + attachment `.png/.jpg/.jpeg/.webp` - parse screenshot broker summary pakai moondream.\n"
            "`/broker` + attachment `.csv` - import broker summary dari CSV.\n"
            "`/scan` - scan broker summary terbaru, filter fundamental, cek Tavily bila perlu, lalu kirim report.\n"
            "`/ask rangkum` - ringkasan broker summary terbaru.\n"
            "`/ask BBCA` - detail ticker dan trend akumulasi 5 data terakhir.\n"
            "`/ask top akumulasi` - ranking akumulasi broker.\n"
            "`/ask foreign net buy` - ranking foreign net buy."
        )

    def _fetch_messages(self) -> list[dict[str, Any]]:
        params = {"limit": 20}
        if self.last_message_id:
            params["after"] = self.last_message_id
        response = requests.get(
            f"{self.API_BASE}/channels/{self.settings.ch_bot}/messages",
            headers=self.headers,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def _get_attachment(self, message: dict[str, Any], allowed_suffixes: set[str]) -> dict[str, Any]:
        for attachment in message.get("attachments", []):
            filename = attachment.get("filename", "")
            if Path(filename).suffix.lower() in allowed_suffixes:
                return attachment
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
        logger.info("Downloaded Discord fundamental file: %s", output)
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
