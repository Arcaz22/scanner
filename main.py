import argparse
import asyncio

from app.core.logging import setup_logging
from app.services.ask_service import AskService
from app.services.scanner_service import ScannerService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swing scanner CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Jalankan scan")
    scan.add_argument("--no-news", action="store_true", help="Lewati Tavily/news lookup")
    scan.add_argument("--no-discord", action="store_true", help="Jangan kirim report ke Discord")

    broker = subparsers.add_parser("broker", help="Update broker summary dari CSV")
    broker.add_argument("--source", required=True, help="Path CSV broker summary")
    screenshot = subparsers.add_parser("broker-screenshot", help="Update broker summary dari screenshot")
    screenshot.add_argument("--source", required=True, help="Path image broker summary")
    ask = subparsers.add_parser("ask", help="Tanya data scanner yang sudah tersimpan di DB")
    ask.add_argument("question", nargs="+", help="Pertanyaan, contoh: ask BBCA atau ask top akumulasi")
    return parser


async def run(args: argparse.Namespace) -> None:
    logger = setup_logging()

    service = ScannerService()

    if args.command == "broker":
        updated = await service.update_broker_summary(source=args.source)
        logger.info("Selesai update broker summary: %s saham", len(updated))
        return

    if args.command == "broker-screenshot":
        updated = await service.update_broker_summary_screenshot(source=args.source)
        logger.info("Selesai parse screenshot broker summary: %s saham", len(updated))
        return

    if args.command == "ask":
        answer = await AskService().answer(" ".join(args.question))
        print(answer)
        return

    if args.command == "scan":
        report = await service.run_daily_scan(include_news=not args.no_news)
        if not args.no_discord:
            result = service.send_daily_report(report)
            if not result.sent:
                logger.warning("Report Discord tidak terkirim: %s", result.message)
        logger.info(
            "Selesai scan: %s signal, %s caution, %s normal",
            len(report.get_signals()),
            len(report.get_cautions()),
            len(report.get_normals()),
        )


if __name__ == "__main__":
    asyncio.run(run(build_parser().parse_args()))
