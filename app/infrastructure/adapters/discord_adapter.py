import requests

from app.core.logging import get_logger
from app.core.settings import Settings, get_settings
from app.domain.enums import SignalStatus
from app.domain.notification import NotificationResult
from app.domain.report import DailyReport

logger = get_logger(__name__)


class DiscordAdapter:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def send_daily_report(self, report: DailyReport) -> NotificationResult:
        content = self._format_report(report)
        return self._send_bot_message(content)

    def _send_bot_message(self, content: str) -> NotificationResult:
        if not self.settings.discord_token or not self.settings.ch_bot:
            message = "DISCORD_TOKEN dan CH_BOT wajib diisi untuk kirim report Discord"
            logger.warning(message)
            return NotificationResult(False, message)

        response = requests.post(
            f"https://discord.com/api/v10/channels/{self.settings.ch_bot}/messages",
            headers={
                "Authorization": f"Bot {self.settings.discord_token}",
                "Content-Type": "application/json",
            },
            json={"content": content},
            timeout=15,
        )
        if response.status_code >= 400:
            logger.error("Discord bot message failed: %s %s", response.status_code, response.text)
            return NotificationResult(False, response.text)
        logger.info("Discord report sent to channel %s", self.settings.ch_bot)
        return NotificationResult(True, "sent via bot")

    def _format_report(self, report: DailyReport) -> str:
        signals = report.get_signals()
        cautions = report.get_cautions()
        normals = report.get_normals()

        lines = [
            f"**Daily Stock Scanner - {report.date:%Y-%m-%d}**",
            f"Signal: {len(signals)} | Caution: {len(cautions)} | Normal: {len(normals)}",
        ]

        flagged = [signal for signal in report.signals if signal.status != SignalStatus.NORMAL]
        if not flagged:
            lines.append("")
            lines.append("Tidak ada signal hari ini.")
            return "\n".join(lines)

        lines.append("")
        for signal in flagged[:15]:
            price = report.price_data.get(signal.ticker)
            broker = report.broker_data.get(signal.ticker)
            close = f"{price.close:,.0f}" if price else "-"
            change = f"{price.price_change_pct:+.2f}%" if price else "-"
            volume_ratio = f"{price.volume_ratio:.2f}x" if price else "-"
            accum = f"{broker.accum_ratio:.2f}x" if broker else "-"
            foreign = self._format_money(broker.net_foreign_val) if broker else "-"
            lines.append(
                f"- **{signal.ticker}** `{signal.status.value}` "
                f"close={close} chg={change} vol={volume_ratio} "
                f"accum={accum} foreign={foreign} "
                f"triggers={signal.triggers_count}"
            )
            if signal.notes:
                lines.append(f"  {signal.notes}")

        if len(flagged) > 15:
            lines.append(f"...dan {len(flagged) - 15} signal lain.")

        content = "\n".join(lines)
        return content[:1900]

    def _format_money(self, value: float) -> str:
        abs_value = abs(value)
        sign = "-" if value < 0 else ""
        if abs_value >= 1_000_000_000:
            return f"{sign}{abs_value / 1_000_000_000:.2f}B"
        if abs_value >= 1_000_000:
            return f"{sign}{abs_value / 1_000_000:.2f}M"
        return f"{value:,.0f}"
