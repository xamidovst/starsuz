"""Log yozish — faylga va konsolga. Maxfiy ma'lumotlar logga tushmaydi."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import BOT_TOKEN, DEBUG, LOG_PATH


class _SecretFilter(logging.Filter):
    """Xabar matnida bot tokeni bo'lsa — uni yashiradi."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return True
        if BOT_TOKEN and BOT_TOKEN in message:
            record.msg = message.replace(BOT_TOKEN, "***TOKEN***")
            record.args = ()
        return True


_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging() -> logging.Logger:
    """Bir martalik log sozlamasi. Qayta chaqirilsa — takrorlanmaydi."""
    root = logging.getLogger("xamidov")
    if root.handlers:
        return root

    root.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    secret_filter = _SecretFilter()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_LOG_FORMAT))
    console.addFilter(secret_filter)
    root.addHandler(console)

    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_PATH,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        file_handler.addFilter(secret_filter)
        root.addHandler(file_handler)
    except OSError:  # faylga yozib bo'lmasa — faqat konsol bilan davom etamiz
        root.warning("Log faylini ochib bo'lmadi: %s", LOG_PATH)

    # Alohida kutubxonalar (aiogram, aiosqlite) xabarlarini pasaytiramiz
    logging.getLogger("aiogram").setLevel(logging.INFO)
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"xamidov.{name}")
