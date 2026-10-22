"""Foydalanuvchi kiritgan ma'lumotlarni tekshirish vositalari."""

from __future__ import annotations

import re
import unicodedata

# Promo-kod: harf, raqam, pastki chiziq. 3-32 belgi.
PROMO_RE = re.compile(r"^[A-Za-z0-9_\-]{3,32}$")
# Telegram ID — faqat musbat butun son
_TG_ID_RE = re.compile(r"^\d{1,20}$")


def parse_int(value, min_value: int | None = None, max_value: int | None = None) -> int | None:
    """Satrni butun songa aylantiradi. Xato bo'lsa None qaytaradi."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    else:
        text = str(value).strip().replace(" ", "").replace("\u00a0", "")
        # 1 000 000 / 1,000,000 kabi yozuvlar — faqat aniq guruhlangan bo'lsa
        if re.fullmatch(r"-?\d{1,3}(?:[.,]\d{3})+", text):
            text = re.sub(r"[.,]", "", text)
        if not text or not re.fullmatch(r"-?\d+", text):
            return None
        try:
            number = int(text)
        except ValueError:
            return None

    if min_value is not None and number < min_value:
        return None
    if max_value is not None and number > max_value:
        return None
    return number


def parse_amount(value, min_value: int = 1, max_value: int = 10**15) -> int | None:
    """Pul / miqdor uchun: faqat musbat butun son."""
    number = parse_int(value, min_value, max_value)
    if number is None or number <= 0:
        return None
    return number


def parse_tg_id(value) -> int | None:
    """Telegram ID tekshiradi (faqat raqamlar)."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value > 0 else None
    text = str(value or "").strip().lstrip("@")
    if _TG_ID_RE.match(text):
        return int(text)
    return None


def clean_text(value, max_len: int = 500) -> str:
    """Matnni xavfli belgilardan tozalaydi va uzunligini cheklaydi."""
    if value is None:
        return ""
    text = str(value)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cc" or ch in ("\n", "\t"))
    text = text.replace("\r\n", "\n").strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text


def clean_line(value, max_len: int = 100) -> str:
    """Bir qatorli matn (nom, izoh) uchun — yangi qatorlarni olib tashlaydi."""
    text = clean_text(value, max_len=max_len)
    return " ".join(text.split())


def normalize_promo(value) -> str | None:
    """Promo-kodni tekshiradi va standart ko'rinishga keltiradi."""
    code = str(value or "").strip().upper()
    if not PROMO_RE.match(code):
        return None
    return code


def format_money(amount: int) -> str:
    """125000 -> '125 000 so'm'"""
    try:
        return f"{int(amount):,}".replace(",", " ") + " so'm"
    except (TypeError, ValueError):
        return str(amount)


def escape_html(value) -> str:
    from html import escape

    return escape(str(value or ""))
