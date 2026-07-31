import logging
import re
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from app.core.settings import get_settings


_LOG_FORMATTER = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _safe_log_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    normalized = normalized.strip("-._")
    return normalized[:80] or "video"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger()
    if getattr(logger, "_scanner_logging_configured", False):
        return logger

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_LOG_FORMATTER)

    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    logger._scanner_logging_configured = True

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logger


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


@contextmanager
def log_file_context(label: str):
    logger = logging.getLogger()
    log_dir = get_settings().log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"{timestamp}_{_safe_log_name(label)}.log"
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(_LOG_FORMATTER)
    logger.addHandler(handler)

    try:
        logger.info("Log file: %s", path)
        yield path
    finally:
        logger.removeHandler(handler)
        handler.close()


video_log_context = log_file_context
