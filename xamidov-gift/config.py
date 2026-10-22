"""XAMIDOV GIFT — bot sozlamalari (.env faylidan o'qiladi)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Loyiha ildiz papkasi
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# .env faylini yuklash
load_dotenv(BASE_DIR / ".env")

DEFAULT_LANG = "uz"
SUPPORTED_LANGS = ("uz", "ru", "en")


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def parse_admin_ids(raw: str) -> frozenset[int]:
    """ADMIN_IDS satridan faqat haqiqiy butun raqamlarni ajratib oladi."""
    ids: set[int] = set()
    for part in raw.replace(";", ",").replace("\n", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if part.lstrip("-").isdigit():
            ids.add(int(part))
    return frozenset(ids)


# --- Asosiy qiymatlar ---
BOT_TOKEN: str = _get("BOT_TOKEN")
BOT_USERNAME: str = _get("BOT_USERNAME").lstrip("@")  # @ belgisiz
ADMIN_IDS: frozenset[int] = parse_admin_ids(_get("ADMIN_IDS"))
DEBUG: bool = _get("DEBUG", "false").lower() in ("1", "true", "yes", "on")

# --- Fayl yo'llari ---
# Render kabi platformalarda disk yo'lini DB_PATH orqali o'zgartirish mumkin
_db_override = os.getenv("DB_PATH", "").strip()
DB_PATH: Path = Path(_db_override) if _db_override else DATA_DIR / "xamidov_gift.db"
LOG_PATH: Path = DATA_DIR / "bot.log"


def validate_config() -> tuple[list[str], list[str]]:
    """Sozlamalarni tekshiradi.

    Returns:
        (fatal_errors, warnings) — fatal xatolar bo'lsa bot ishga tushmaydi.
    """
    fatal: list[str] = []
    warn: list[str] = []

    if not BOT_TOKEN or len(BOT_TOKEN) < 30 or ":" not in BOT_TOKEN:
        fatal.append(
            "BOT_TOKEN to'g'ri kiritilmagan.\n"
            "   → Telegram'da @BotFather oching, /newbot yozing va token oling.\n"
            "   → Uni .env faylidagi BOT_TOKEN qatoriga yozing."
        )

    if not ADMIN_IDS:
        fatal.append(
            "ADMIN_IDS bo'sh.\n"
            "   → .env faylida ADMIN_IDS=123456789 deb yozing (raqamingiz @userinfobot da)."
        )

    if not BOT_USERNAME:
        warn.append(
            "BOT_USERNAME kiritilmagan — referal havola to'g'ri yaratilmaydi.\n"
            "   → .env ichida BOT_USERNAME=masalan_bot deb qo'shing."
        )

    return fatal, warn
