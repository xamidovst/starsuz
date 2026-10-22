"""To'lovlar: chek qabuli, admin tasdiqlashi va Telegram Stars invoice.

Xavfsizlik:
* chek maxfiy identifikatori (receipt_key) — bir chek ikki marta ishlatilmaydi;
* approve faqat bajariladi (status 'pending' → 'approved'), ikki marta emas;
* Telegram Stars to'lovi `telegram_payment_charge_id` unikalligi bilan himoyalangan.
"""

from __future__ import annotations

import hashlib
import json
import re

from aiogram.types import LabeledPrice, Message

from database import db
from services import referral_service
from utils.logger import get_logger

log = get_logger("payment")

_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")


# --------------------------------------------------------------- to'lov usullari
def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")
    return slug or "method"


async def get_methods(include_inactive: bool = False) -> list[dict]:
    raw = await db.get_setting("payment_methods", "[]") or "[]"
    try:
        methods = json.loads(raw)
    except (ValueError, TypeError):
        log.warning("payment_methods sozlamasi buzilgan, bo'sh ro'yxat ishlatiladi")
        methods = []
    if not isinstance(methods, list):
        return []
    clean = [m for m in methods if isinstance(m, dict) and m.get("id") and m.get("name")]
    if include_inactive:
        return clean
    return [m for m in clean if m.get("active", True)]


async def save_methods(methods: list[dict]) -> None:
    await db.set_setting("payment_methods", json.dumps(methods, ensure_ascii=False))


async def get_method(method_id: str) -> dict | None:
    for method in await get_methods(include_inactive=True):
        if str(method["id"]) == str(method_id):
            return method
    return None


async def add_method(name: str, details: str = "") -> dict:
    methods = await get_methods(include_inactive=True)
    method_id = _slug(name)
    while any(str(m["id"]) == method_id for m in methods):
        method_id = _slug(name) + "_" + str(len(methods) + 1)
    method = {"id": method_id, "name": name, "details": details, "active": True}
    methods.append(method)
    await save_methods(methods)
    return method


async def update_method(method_id: str, **fields) -> dict | None:
    methods = await get_methods(include_inactive=True)
    for method in methods:
        if str(method["id"]) == str(method_id):
            method.update({k: v for k, v in fields.items() if k in ("name", "details", "active")})
            await save_methods(methods)
            return method
    return None


async def remove_method(method_id: str) -> bool:
    methods = await get_methods(include_inactive=True)
    remaining = [m for m in methods if str(m["id"]) != str(method_id)]
    if len(remaining) == len(methods):
        return False
    await save_methods(remaining)
    return True


# ------------------------------------------------------------------------ chek
def receipt_from_message(message: Message) -> tuple[str, str] | None:
    """Xabardan chek identifikatorini yasaydi. Returns: (key, ref) yoki None."""
    if message.photo:
        file_id = message.photo[-1].file_id
        return "f:" + hashlib.sha256(file_id.encode()).hexdigest(), file_id[:80]

    document = message.document
    if document:
        name = (document.file_name or "").lower()
        mime = (document.mime_type or "").lower()
        if name.endswith(_IMAGE_EXT) or mime.startswith("image/"):
            file_id = document.file_id
            return "f:" + hashlib.sha256(file_id.encode()).hexdigest(), file_id[:80]
        return None

    if message.text:
        normalized = " ".join(message.text.split()).lower()
        if not normalized:
            return None
        # Matnli chek: faqat shu foydalanuvchi uchun takrorlanish bloklanadi
        payload = f"{message.from_user.id}:{normalized}"
        return "t:" + hashlib.sha256(payload.encode()).hexdigest(), normalized[:80]

    return None


async def create_topup_request(user_id: int, method_name: str, amount: int) -> int | None:
    """Foydalanuvchi chek yuborishga tayyor — to'lov yaratiladi (pending)."""
    payment_id = await db.create_payment(user_id, method_name, int(amount))
    if payment_id:
        log.info("Yangi to'lov so'rovi: #%s (user=%s, %s so'm)", payment_id, user_id, amount)
    return payment_id


async def submit_receipt(payment_id: int, key: str, ref: str) -> str | None:
    """Chekni bog'laydi. None = muvaffaqiyatli, aks holda xato xabari."""
    error = await db.attach_receipt(payment_id, key, ref)
    if error:
        log.info("Chek rad etildi (#%s): %s", payment_id, error)
    return error


async def approve(payment_id: int, admin_id: int) -> tuple[bool, str, int | None]:
    """Chekni tasdiqlash. Returns: (ok, xabar, foydalanuvchi_id)."""
    payment = await db.get_payment(payment_id)
    if payment is None:
        return False, "To'lov topilmadi", None

    ok, result = await db.approve_payment(payment_id, admin_id)
    if not ok:
        return False, str(result), int(payment["user_id"])

    user_id = int(payment["user_id"])
    await referral_service.on_first_purchase(user_id)
    log.info("To'lov tasdiqlandi: #%s (+%s so'm, user=%s)", payment_id, payment["amount"], user_id)
    return True, f"Balans {result} so'mga oshirildi ✅", user_id


async def reject(payment_id: int, admin_id: int, note: str = "") -> tuple[bool, str, int | None]:
    payment = await db.get_payment(payment_id)
    if payment is None:
        return False, "To'lov topilmadi", None
    ok, result = await db.reject_payment(payment_id, admin_id, note)
    return ok, str(result), int(payment["user_id"]) if payment else None


def payment_text(payment: dict) -> str:
    status = {"pending": "🕓 Tekshiruvda", "approved": "✅ Tasdiqlandi", "rejected": "❌ Rad etildi"}
    lines = [
        f"💳 To'lov cheki #{payment['id']}",
        f"Foydalanuvchi: {payment['user_id']}",
        f"Summa: {int(payment['amount']):,} so'm".replace(",", " "),
        f"Usul: {payment['method']}",
        f"Holat: {status.get(payment['status'], payment['status'])}",
        f"Sana: {payment['created_at']} UTC",
    ]
    if payment.get("receipt_ref"):
        lines.append(f"Chek: {payment['receipt_ref']}")
    if payment.get("note"):
        lines.append(f"Izoh: {payment['note']}")
    return "\n".join(lines)


# --------------------------------------------------------------- Telegram Stars
def stars_payload(user_id: int, stars: int) -> str:
    return f"topup:{user_id}:{stars}"


def parse_stars_payload(payload: str | None) -> tuple[int, int] | None:
    if not payload:
        return None
    parts = str(payload).split(":")
    if len(parts) != 3 or parts[0] != "topup":
        return None
    if not parts[1].isdigit() or not parts[2].isdigit():
        return None
    user_id, stars = int(parts[1]), int(parts[2])
    if user_id <= 0 or stars <= 0 or stars > 100_000:
        return None
    return user_id, stars


async def stars_presets() -> list[int]:
    raw = await db.get_setting("stars_topup_presets", "15,50,100,250") or ""
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit() and 0 < int(part) <= 100_000:
            values.append(int(part))
    return values or [15, 50, 100, 250]


async def stars_rate() -> int:
    return await db.get_int_setting("stars_topup_rate", 0)


def stars_prices(stars: int) -> list[LabeledPrice]:
    """XTR invoice: amount = yulduzlar soni (Telegram valyutasi)."""
    return [LabeledPrice(label=f"{stars} ⭐", amount=int(stars))]


async def credit_stars(user_id: int, stars: int, charge_id: str) -> tuple[bool, int]:
    """Stars orqali to'lovni bir marta hisobga oshiradi. Returns: (ok, qo'shilgan so'm)."""
    rate = await stars_rate()
    amount_uzs = int(stars) * max(rate, 0)
    if amount_uzs <= 0:
        log.warning("Stars kursi noto'g'ri sozlangan (rate=%s), to'lov hisoblanmadi", rate)
        return False, 0

    payment_id = await db.credit_charge(charge_id, int(user_id), amount_uzs, int(stars))
    if payment_id is None:
        return False, 0

    await referral_service.on_first_purchase(int(user_id))
    log.info("Stars to'lovi qabul qilindi: user=%s, %s ⭐ = %s so'm", user_id, stars, amount_uzs)
    return True, amount_uzs


__all__ = [
    "get_methods", "save_methods", "get_method", "add_method", "update_method",
    "remove_method", "receipt_from_message", "create_topup_request", "submit_receipt",
    "approve", "reject", "payment_text", "stars_payload", "parse_stars_payload",
    "stars_presets", "stars_rate", "stars_prices", "credit_stars",
]
