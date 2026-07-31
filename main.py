import argparse
import asyncio

from app.core.logging import setup_logging
from app.services.ask_service import AskService
from app.services.scanner_service import ScannerService
from app.services.watchlist_service import WatchlistService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swing scanner CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Jalankan scan")
    scan.add_argument("--no-news", action="store_true", help="Lewati Tavily/news lookup")
    scan.add_argument("--no-discord", action="store_true", help="Jangan kirim report ke Discord")

    intraday = subparsers.add_parser("intraday-scan", help="Jalankan scanner intraday")
    intraday.add_argument("--no-news", action="store_true", help="Lewati Tavily/news lookup")
    intraday.add_argument("--no-discord", action="store_true", help="Jangan kirim report ke Discord")

    broker = subparsers.add_parser("broker", help="Update broker summary dari CSV")
    broker.add_argument("--source", required=True, help="Path CSV broker summary")
    ask = subparsers.add_parser("ask", help="Tanya data scanner yang sudah tersimpan di DB")
    ask.add_argument("question", nargs="+", help="Pertanyaan, contoh: ask BBCA atau ask top akumulasi")
    subparsers.add_parser("watchlist", help="Tampilkan ticker watchlist")
    return parser


async def run(args: argparse.Namespace) -> None:
    logger = setup_logging()

    if args.command == "watchlist":
        for saham in WatchlistService().list_saham():
            print(f"{saham.ticker}\t{saham.nama}\t{saham.risk_level.value}")
        return

    service = ScannerService()

    if args.command == "broker":
        updated = await service.update_broker_summary(source=args.source)
        logger.info("Selesai update broker summary: %s saham", len(updated))
        return

    if args.command == "ask":
        answer = await AskService().answer(" ".join(args.question))
        print(answer)
        return

    if args.command in {"scan", "intraday-scan"}:
        report = await service.run_intraday_scan(include_news=not args.no_news)
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
