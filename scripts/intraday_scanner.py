"""
Run intraday scanner.

Cron example:
  */15 9-16 * * 1-5 cd /path/to/scanner && python scripts/intraday_scanner.py
"""

import argparse
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import setup_logging
from app.services.scanner_service import ScannerService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scanner berbasis DB fundamental + broker summary")
    parser.add_argument("--no-news", action="store_true", help="Lewati Tavily/news lookup")
    parser.add_argument("--no-discord", action="store_true", help="Jangan kirim report ke Discord")
    return parser


async def main() -> None:
    args = build_parser().parse_args()
    logger = setup_logging()
    service = ScannerService()
    report = await service.run_intraday_scan(include_news=not args.no_news)

    if not args.no_discord:
        result = service.send_daily_report(report)
        if not result.sent:
            logger.warning("Report Discord tidak terkirim: %s", result.message)

    logger.info("Intraday scan complete: %s signal", len(report.signals))


if __name__ == "__main__":
    asyncio.run(main())
