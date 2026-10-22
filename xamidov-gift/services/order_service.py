"""Buyurtmalar: yaratish, balans bilan to'lash, holatini boshqarish."""

from __future__ import annotations

import json

from database import ORDER_STATUSES, db
from services import referral_service
from utils.logger import get_logger
from utils.validators import format_money

log = get_logger("order")

PTYPE_LABELS = {"stars": "⭐ Telegram Stars", "premium": "💎 Telegram Premium", "gift": "🎁 Telegram sovg'asi"}


class OrderError(Exception):
    """Buyurtma bilan bog'liq foydalanuvchi xatosi (xabar ko'rsatiladi)."""


def product_meta(product: dict) -> dict:
    raw = product.get("meta") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def catalog_text(ptype: str, products: list[dict]) -> str:
    title = PTYPE_LABELS.get(ptype, ptype)
    lines = [f"{title} — katalog", ""]
    if not products:
        lines.append("Hozircha mahsulot yo'q.")
    else:
        for product in products:
            meta = product_meta(product)
            price = int(product.get("price") or 0)
            if meta.get("custom"):
                lines.append(f"✍️ {product['name']} — o'zingiz miqdorni kiriting")
            elif price > 0:
                lines.append(f"• {product['name']} — {format_money(price)}")
            else:
                lines.append(f"• {product['name']} — ⏳ narx belgilanmagan")
    lines.append("")
    lines.append("Mahsulotni tanlang 👇")
    return "\n".join(lines)


def product_detail_text(product: dict) -> str:
    meta = product_meta(product)
    price = int(product.get("price") or 0)
    lines = [f"📦 {product['name']}", ""]

    if product.get("description"):
        lines += [product["description"], ""]

    if product.get("ptype") == "stars" and meta.get("stars"):
        lines.append(f"Miqdor: {meta['stars']} ⭐")
    if product.get("ptype") == "premium" and meta.get("days"):
        lines.append(f"Muddat: {meta['days']} kun")

    if meta.get("custom"):
        lines += ["", "✍️ O'zingizga kerakli miqdorni kiriting.", f"Narx: 1 ⭐ = so'mda admin tomonidan belgilanadi."]
    elif price > 0:
        lines += ["", f"💰 Narx: {format_money(price)}"]
    else:
        lines += ["", "⏳ Narx hali belgilanmagan.", "Admin tomonidan tez orada belgilanadi."]
    return "\n".join(lines)


def order_text(order: dict) -> str:
    status = ORDER_STATUSES.get(order["status"], order["status"])
    try:
        details = json.loads(order.get("details") or "{}")
    except (ValueError, TypeError):
        details = {}

    lines = [
        f"🧾 Buyurtma {order['order_no']}",
        "",
        f"Mahsulot: {order['product_name']}",
        f"Narx: {format_money(order['amount'])}",
        f"Holat: {status}",
    ]
    if details.get("stars"):
        lines.append(f"Miqdor: {details['stars']} ⭐")
    if details.get("username"):
        lines.append(f"Foydalanuvchi: {details['username']}")
    if order.get("paid_via") == "balance":
        lines.append("To'lov: 💰 Balansdan")
    if order.get("admin_note"):
        lines.append(f"Izoh: {order['admin_note']}")
    lines += ["", f"Yaratilgan: {order['created_at']} UTC"]
    return "\n".join(lines)


async def create_order(
    user_id: int,
    ptype: str,
    product_name: str,
    amount: int,
    product_id: int | None = None,
    details: dict | None = None,
) -> dict:
    """Buyurtma yaratadi (holat: 💳 To'lov kutilmoqda)."""
    if amount <= 0:
        raise OrderError("Narx belgilanmagan — buyurtma berib bo'lmaydi.")
    order = await db.create_order(
        user_id=user_id,
        ptype=ptype,
        product_name=product_name,
        amount=int(amount),
        product_id=product_id,
        details=details,
    )
    log.info("Yangi buyurtma: %s (user=%s, %s so'm)", order.get("order_no"), user_id, amount)
    return order


async def get_owned_order(order_no: str, user_id: int) -> dict:
    """Faqat shu foydalanuvchining buyurtmasini oladi (boshqasiniki emas)."""
    order = await db.get_order_by_no(order_no)
    if order is None:
        raise OrderError("Buyurtma topilmadi.")
    if int(order["user_id"]) != int(user_id):
        log.warning("Boshqa foydalanuvchining buyurtmasiga urinish: user=%s order=%s", user_id, order_no)
        raise OrderError("Bu buyurtma sizga tegishli emas.")
    return order


async def pay_with_balance(order_no: str, user_id: int) -> tuple[bool, dict | None, str]:
    """Balansdan to'lash (atomar: mablag' yetmasa — hech narsa o'zgarmaydi)."""
    try:
        order = await get_owned_order(order_no, user_id)
    except OrderError as exc:
        return False, None, str(exc)

    if order["status"] != "awaiting_payment":
        return False, order, f"Bu buyurtma allaqachon holatda: {ORDER_STATUSES.get(order['status'], order['status'])}"

    amount = int(order["amount"])
    if amount > 0:
        try:
            await db.add_balance(
                user_id,
                -amount,
                ttype="purchase",
                note=f"Buyurtma {order['order_no']} uchun to'lov",
                ref_id=order["id"],
            )
        except ValueError:
            return False, order, (
                f"Balans mablag'i yetarli emas.\n"
                f"Kerakli: {format_money(amount)}\n"
                f"Avval «💳 Hisobni to'ldirish» bo'limidan foydalaning."
            )

    await db.set_order_status(order["id"], "pending", paid_via="balance")
    order = await db.get_order(order["id"])

    # Referal bonusni faollashtirish (birinchi haqiqiy xarid)
    await referral_service.on_first_purchase(user_id)

    log.info("Buyurtma to'landi: %s (user=%s)", order_no, user_id)
    return True, order, "To'lov qabul qilindi! ✅"


async def cancel_order(order_no: str, user_id: int) -> tuple[bool, dict | None, str]:
    """Foydalanuvchi o'z buyurtmasini bekor qiladi (to'langan bo'lsa — pul qaytadi)."""
    try:
        order = await get_owned_order(order_no, user_id)
    except OrderError as exc:
        return False, None, str(exc)

    if order["status"] in ("completed", "cancelled"):
        return False, order, f"Buyurtma allaqachon: {ORDER_STATUSES.get(order['status'])}"
    if order["status"] == "processing":
        return False, order, "Buyurtma bajarilmoqda. Bekor qilish uchun admin bilan bog'laning."

    refunded = False
    if order["status"] == "pending" and order.get("paid_via") == "balance" and int(order["amount"]) > 0:
        await db.add_balance(
            user_id,
            int(order["amount"]),
            ttype="refund",
            note=f"Buyurtma {order['order_no']} bekor qilindi (foydalanuvchi)",
            ref_id=order["id"],
        )
        refunded = True

    await db.set_order_status(order["id"], "cancelled", admin_note="Foydalanuvchi bekor qildi")
    order = await db.get_order(order["id"])
    text = "Buyurtma bekor qilindi ❌"
    if refunded:
        text += f"\nTo'langan {format_money(order['amount'])} balansga qaytarildi."
    return True, order, text


async def admin_change_status(
    order: dict,
    new_status: str,
    admin_id: int,
    note: str = "",
) -> tuple[bool, str]:
    """Admin tomonidan holat o'zgartirish. Rad etilsa — balans qaytariladi."""
    if new_status not in ORDER_STATUSES:
        return False, "Noto'g'ri holat"

    # Eng oxirgi holatni bazadan olamiz (eski ma'lumot bilan ishlamaymiz)
    fresh = await db.get_order(int(order["id"]))
    if fresh is not None:
        order = fresh

    if order["status"] == new_status:
        return False, "Buyurtma allaqachon shu holatda"

    refunded = False
    if new_status == "cancelled" and order.get("paid_via") == "balance" and int(order["amount"]) > 0:
        if order["status"] in ("pending", "processing", "awaiting_payment"):
            await db.add_balance(
                int(order["user_id"]),
                int(order["amount"]),
                ttype="refund",
                note=f"Buyurtma {order['order_no']} admin tomonidan rad etildi",
                ref_id=order["id"],
            )
            refunded = True

    await db.set_order_status(order["id"], new_status, admin_note=note or None)
    await db.add_log(
        admin_id,
        "order_status",
        f"{order['order_no']}: {order['status']} → {new_status}"
        + (f" | {note}" if note else "")
        + (" | pul qaytarildi" if refunded else ""),
    )
    updated = await db.get_order(order["id"])
    text = f"Buyurtma {order['order_no']}: {ORDER_STATUSES[new_status]}"
    if refunded:
        text += f"\n💰 {format_money(order['amount'])} foydalanuvchiga qaytarildi."
    return True, text + (f"\nIzoh: {note}" if note else "")


async def open_catalog(event, ptype: str) -> None:
    """Bo'lim katalogini ko'rsatadi (Message yoki CallbackQuery uchun)."""
    from keyboards.inline import products_kb
    from utils.helpers import send

    products = await db.list_products(ptype, active_only=True)
    text = catalog_text(ptype, products)
    await send(event, text, products_kb(ptype, products, back_data="menu"))


async def open_product(event, ptype: str, product_id: int) -> None:
    """Bitta mahsulot tafsilotini ko'rsatadi."""
    from keyboards.inline import product_detail_kb
    from utils.helpers import send

    product = await db.get_product(product_id)
    if product is None or product["ptype"] != ptype or not int(product["is_active"]):
        await send(event, "Mahsulot topilmadi yoki o'chirilgan.", None)
        return
    await send(event, product_detail_text(product), product_detail_kb(ptype, product))


async def place_order(
    event,
    bot,
    ptype: str,
    product_name: str,
    amount: int,
    product_id: int | None = None,
    details: dict | None = None,
) -> dict | None:
    """Buyurtma yaratadi, foydalanuvchiga ko'rsatadi va adminlarga xabar beradi."""
    from aiogram.types import CallbackQuery
    from keyboards.inline import admin_order_kb, order_actions_kb
    from utils.helpers import notify_admins, send

    user = getattr(event, "from_user", None)
    if user is None:
        return None

    try:
        order = await create_order(
            user_id=user.id,
            ptype=ptype,
            product_name=product_name,
            amount=amount,
            product_id=product_id,
            details=details,
        )
    except OrderError as exc:
        await send(event, str(exc), None)
        return None

    await send(event, order_text(order), order_actions_kb(order["order_no"]))

    admin_text = (
        "📦 YANGI BUYURTMA\n"
        f"Raqam: {order['order_no']}\n"
        f"Foydalanuvchi: {order['user_id']}\n"
        f"Mahsulot: {product_name}\n"
        f"Narx: {format_money(amount)}\n"
        "Holat: 💳 To'lov kutilmoqda"
    )
    await notify_admins(bot, admin_text, admin_order_kb(order["id"]))

    if isinstance(event, CallbackQuery):
        log.info("Buyurtma yaratildi: %s (user=%s)", order["order_no"], user.id)
    return order


__all__ = [
    "OrderError",
    "PTYPE_LABELS",
    "product_meta",
    "catalog_text",
    "product_detail_text",
    "order_text",
    "create_order",
    "get_owned_order",
    "pay_with_balance",
    "cancel_order",
    "admin_change_status",
    "open_catalog",
    "open_product",
    "place_order",
]
