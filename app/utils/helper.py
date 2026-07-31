import json
from typing import Optional

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)


def normalize_ticker(ticker: str) -> str:
    """Return canonical IDX ticker without provider suffix."""
    return ticker.strip().upper().removesuffix(".JK")


def load_watchlist() -> list[dict]:
    """Baca watchlist dari JSON, return list of dict."""
    path = get_settings().watchlist_path
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        saham = data.get("saham", [])
        for item in saham:
            item["ticker"] = normalize_ticker(item.get("ticker", ""))
        return saham
    except FileNotFoundError:
        logger.error("watchlist.json tidak ditemukan: %s", path)
        return []


def save_watchlist(saham_list: list[dict]) -> None:
    """Simpan watchlist ke JSON."""
    path = get_settings().watchlist_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"saham": saham_list}, f, indent=2)
    logger.info(f"Watchlist disimpan: {len(saham_list)} saham")


def add_saham(ticker: str, nama: str = "", catatan: str = "") -> bool:
    """Tambah saham baru. Return True jika berhasil."""
    ticker = normalize_ticker(ticker)

    saham_list = load_watchlist()
    if ticker in [s["ticker"] for s in saham_list]:
        logger.warning(f"{ticker} sudah ada di watchlist")
        return False

    saham_list.append({
        "ticker": ticker,
        "nama": nama,
        "risk_level": "unknown",
        "catatan": catatan
    })
    save_watchlist(saham_list)
    logger.info(f"{ticker} ditambahkan ke watchlist")
    return True


def remove_saham(ticker: str) -> bool:
    """Hapus saham. Return True jika berhasil."""
    ticker = normalize_ticker(ticker)

    saham_list = load_watchlist()
    new_list = [s for s in saham_list if s["ticker"] != ticker]

    if len(new_list) == len(saham_list):
        logger.warning(f"{ticker} tidak ditemukan di watchlist")
        return False

    save_watchlist(new_list)
    logger.info(f"{ticker} dihapus dari watchlist")
    return True


def update_risk_level(ticker: str, risk_level: str, catatan: str = "") -> None:
    """Update risk level saham."""
    ticker = normalize_ticker(ticker)

    saham_list = load_watchlist()
    for saham in saham_list:
        if saham["ticker"] == ticker:
            saham["risk_level"] = risk_level
            if catatan:
                saham["catatan"] = catatan
            break

    save_watchlist(saham_list)


def get_tickers() -> list[str]:
    """Return list ticker strings saja."""
    return [s["ticker"] for s in load_watchlist()]


def get_saham_info(ticker: str) -> Optional[dict]:
    """Return info saham by ticker, None jika tidak ada."""
    ticker = normalize_ticker(ticker)

    for saham in load_watchlist():
        if saham["ticker"] == ticker:
            return saham
    return None
