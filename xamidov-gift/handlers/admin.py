""" professional admin panel.

Barcha `adm:` callback va /admin buyrug'i shu yerda.
Router darajasida admin filtri bor — oddiy foydalanuvchi kira olmaydi.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import ORDER_STATUSES, PAYMENT_STATUSES, PTYPE_GIFT, PTYPE_PREMIUM, PTYPE_STARS, db
from handlers.start import show_main_menu
from keyboards.back_kbd import back_reply_kb
from keyboards.inline import (
    admin_back_kb,
    admin_menu_kb,
    admin_method_item_kb,
    admin_methods_kb,
    admin_order_kb,
    admin_orders_kb,
    admin_payment_kb,
    admin_payments_kb,
    admin_product_kb,
    admin_products_kb,
    admin_promo_item_kb,
    admin_promo_kb,
    admin_settings_kb,
    admin_user_kb,
    admin_users_kb,
    back_kb,
    menu_kb,
    yes_no_kb,
)
from keyboards.main_menu import is_menu_text, main_menu_keyboard
from services import order_service, payment_service, referral_service
from utils.helpers import admin_filter, safe_send, safe_send_photo, send
from utils.i18n import t
from utils.logger import get_logger
from utils.validators import (
    clean_line,
    clean_text,
    format_money,
    normalize_promo,
    parse_amount,
    parse_int,
    parse_tg_id,
)

log = get_logger("admin")
router = Router()

# Router darajasidagi himoya: faqat .env dagi ADMIN_IDS
router.message.filter(admin_filter)
router.callback_query.filter(admin_filter)

PTYPE_NAMES = {PTYPE_STARS: "Stars", PTYPE_PREMIUM: "Premium", PTYPE_GIFT: "Sovg'alar"}
_INT_SETTINGS = {
    "referral_bonus",
    "stars_unit_price",
    "stars_topup_rate",
    "min_topup",
    "max_topup",
    "custom_stars_min",
    "custom_stars_max",
    "broadcast_delay_ms",
}


class AdminSG(StatesGroup):
    user_search = State()
    bal_user = State()
    bal_amount = State()
    prod_name = State()
    prod_price = State()
    prod_image = State()
    price_edit = State()
    promo_code = State()
    promo_bonus = State()
    promo_days = State()
    promo_uses = State()
    promo_per_user = State()
    bcast = State()
    setting = State()
    method_name = State()
    method_details = State()
    method_edit = State()


_broadcast_lock = asyncio.Lock()


# ============================================================== panel menyusi
def _stats_line(label: str, value) -> str:
    return f"{label}: {value}"


async def _panel_text() -> str:
    stats = await db.general_stats()
    lines = [
        "⚙️ ADMIN PANEL",
        "",
        _stats_line("👥 Foydalanuvchilar", stats["users"]),
        _stats_line("📦 Buyurtmalar (jami)", stats["orders_total"]),
        "   " + " | ".join(
            f"{ORDER_STATUSES[s].split(' ')[0]} {stats['orders_by_status'][s]}"
            for s in ("awaiting_payment", "pending", "processing", "completed", "cancelled")
        ),
        _stats_line("💳 Kutilayotgan to'lovlar", stats["pending_payments"]),
        _stats_line("💰 Savdo", format_money(stats["revenue"])),
        _stats_line("🏦 Balanslar jami", format_money(stats["total_balance"])),
        _stats_line("👥 Referallar", f"{stats['referrals']['total']} / faol {stats['referrals']['active']}"),
    ]
    if stats["products_without_price"]:
        lines.append(f"\n⚠️ {stats['products_without_price']} ta mahsulot narxi belgilanmagan!")
    lines.append("\nBo'limni tanlang 👇")
    return "\n".join(lines)


@router.message(Command("admin"))
async def admin_menu_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(await _panel_text(), reply_markup=admin_menu_kb())
    log.info("Admin panel ochildi: %s", message.from_user.id)


@router.callback_query(F.data == "adm:menu")
async def admin_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send(callback, await _panel_text(), admin_menu_kb())


# ================================================================= statistika
@router.callback_query(F.data == "adm:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    stats = await db.general_stats()
    orders = await db.list_recent_orders(10)
    lines = ["📊 STATISTIKA", ""]
    lines.append(f"👥 Foydalanuvchilar: {stats['users']}")
    lines.append(f"📦 Buyurtmalar: {stats['orders_total']}")
    for status, label in ORDER_STATUSES.items():
        lines.append(f"   {label}: {stats['orders_by_status'][status]}")
    lines.append(f"💳 Tekshiruvdagi to'lovlar: {stats['pending_payments']}")
    lines.append(f"💰 Savdo (jami): {format_money(stats['revenue'])}")
    lines.append(f"🏦 Barcha balanslar: {format_money(stats['total_balance'])}")
    lines.append(f"👥 Referallar: jami {stats['referrals']['total']}, faol {stats['referrals']['active']}")
    lines.append(f"💸 Berilgan referal bonus: {format_money(stats['referrals']['paid'])}")
    if orders:
        lines += ["", "🕓 Oxirgi buyurtmalar:"]
        for order in orders:
            lines.append(
                f"• {order['order_no']} — {ORDER_STATUSES.get(order['status'], order['status'])}"
                f" ({format_money(order['amount'])})"
            )
    await send(callback, "\n".join(lines), admin_back_kb())


# ========================================================== foydalanuvchilar
@router.callback_query(F.data == "adm:users")
async def admin_users(callback: CallbackQuery) -> None:
    users = await db.list_recent_users(10)
    text = "👥 OXIRGI FOYDALANUVCHILAR\n\n" + (
        "\n".join(
            f"• @{u['username'] or '—'} | {u['telegram_id']} | {format_money(u['balance'])}"
            for u in users
        )
        if users
        else "Hozircha foydalanuvchi yo'q."
    )
    await send(callback, text, admin_users_kb(users))


@router.callback_query(F.data == "adm:search")
async def admin_search_ask(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.user_search)
    await send(
        callback,
        "🔍 FOYDALANUVCHI QIDIRISH\n\nTelegram ID yoki @username yuboring.\nBekor qilish: /cancel",
        back_reply_kb(),
    )


@router.message(AdminSG.user_search, Command("cancel"))
async def admin_search_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.user_search)
async def admin_search_result(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    await state.clear()
    target = parse_tg_id(message.text)
    user = await db.get_user(target) if target else None
    if user is None:
        await message.answer("❌ Foydalanuvchi topilmadi.", reply_markup=back_reply_kb())
        return
    await message.answer(await _user_card(user), reply_markup=admin_user_kb(int(user["telegram_id"]), bool(user["is_banned"])))


async def _user_card(user: dict) -> str:
    stats = await referral_service.user_stats(int(user["telegram_id"]))
    orders_count = await db.count_orders(user_id=int(user["telegram_id"]))
    return (
        "👤 FOYDALANUVCHI\n\n"
        f"Ism: {user.get('full_name') or '—'}\n"
        f"Username: @{user['username'] or '—'}\n"
        f"ID: {user['telegram_id']}\n"
        f"Balans: {format_money(user['balance'])}\n"
        f"Ro'yxat: {user['created_at']} UTC\n"
        f"Buyurtmalar: {orders_count}\n"
        f"Takliflar: {stats['invited']} (faol {stats['active']})\n"
        f"Promo bonus: {format_money(user.get('promo_bonus_total') or 0)}\n"
        f"Holat: {'🚫 bloklangan' if user['is_banned'] else '✅ faol'}"
    )


@router.callback_query(F.data.startswith("adm:u:"))
async def admin_user_card(callback: CallbackQuery) -> None:
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return
    user = await db.get_user(int(raw_id))
    if user is None:
        await send(callback, "Foydalanuvchi topilmadi.", admin_back_kb("adm:users"))
        return
    await send(callback, await _user_card(user), admin_user_kb(int(user["telegram_id"]), bool(user["is_banned"])))


@router.callback_query(F.data.startswith("adm:ban:"))
async def admin_toggle_ban(callback: CallbackQuery) -> None:
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return
    user = await db.get_user(int(raw_id))
    if user is None:
        await send(callback, "Foydalanuvchi topilmadi.", admin_back_kb("adm:users"))
        return
    banned = not bool(user["is_banned"])
    await db.set_banned(int(raw_id), banned)
    await db.add_log(callback.from_user.id, "ban", f"user={raw_id} banned={banned}")
    log.info("Ban o'zgartirildi: user=%s → %s (admin=%s)", raw_id, banned, callback.from_user.id)
    await send(
        callback,
        f"{'🚫 Bloklandi' if banned else '✅ Blokdan chiqarildi'}: {raw_id}",
        admin_user_kb(int(raw_id), banned),
    )


@router.callback_query(F.data.startswith("adm:uorders:"))
async def admin_user_orders(callback: CallbackQuery) -> None:
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return
    orders = await db.list_user_orders(int(raw_id), limit=10)
    if not orders:
        await send(callback, "Bu foydalanuvchida buyurtma yo'q.", admin_back_kb("adm:users"))
        return
    lines = [f"📦 {raw_id} — buyurtmalar:"]
    for order in orders:
        lines.append(
            f"• {order['order_no']} | {order['product_name']} | {format_money(order['amount'])}\n"
            f"   {ORDER_STATUSES.get(order['status'], order['status'])}"
        )
    await send(callback, "\n".join(lines), admin_back_kb(f"adm:u:{raw_id}"))


# ================================================================== buyurtmalar
@router.callback_query(F.data == "adm:orders")
async def admin_orders(callback: CallbackQuery) -> None:
    orders = await db.list_recent_orders(15)
    text = "📦 OXIRGI BUYURTMALAR\n\n" + (
        "\n".join(
            f"• {o['order_no']} | {o['user_id']} | {format_money(o['amount'])} | "
            f"{ORDER_STATUSES.get(o['status'], o['status'])}"
            for o in orders
        )
        if orders
        else "Buyurtmalar yo'q."
    )
    await send(callback, text, admin_orders_kb(orders))


@router.callback_query(F.data.startswith("adm:ol:"))
async def admin_orders_by_status(callback: CallbackQuery) -> None:
    status = callback.data.split(":")[-1]
    if status not in ORDER_STATUSES:
        await send(callback, t("invalid_input"))
        return
    orders = await db.list_orders_by_status(status, limit=20)
    text = f"{ORDER_STATUSES[status]}\n\n" + (
        "\n".join(
            f"• {o['order_no']} | {o['user_id']} | {format_money(o['amount'])}" for o in orders
        )
        if orders
        else "Bo'sh."
    )
    await send(callback, text, admin_orders_kb(orders, status=status))


@router.callback_query(F.data.startswith("adm:o:"))
async def admin_order(callback: CallbackQuery, bot: Bot) -> None:
    parts = callback.data.split(":")
    # adm:o:<id>  yoki  adm:o:<id>:<status>
    if len(parts) not in (3, 4) or not parts[2].isdigit():
        await send(callback, t("invalid_input"))
        return
    order = await db.get_order(int(parts[2]))
    if order is None:
        await send(callback, "Buyurtma topilmadi.", admin_back_kb("adm:orders"))
        return

    if len(parts) == 4:
        new_status = parts[3]
        ok, text = await order_service.admin_change_status(order, new_status, callback.from_user.id)
        await callback.answer(text.split("\n")[0], show_alert=False)
        if ok:
            user_text = f"📦 Buyurtma {order['order_no']}: {ORDER_STATUSES[new_status]}"
            if new_status == "cancelled" and order.get("paid_via") == "balance":
                user_text += f"\nTo'langan {format_money(order['amount'])} balansga qaytarildi."
            await safe_send(bot, int(order["user_id"]), user_text)
            log.info("Buyurtma holati: %s → %s (admin=%s)", order["order_no"], new_status, callback.from_user.id)
            order = await db.get_order(order["id"]) or order
        else:
            await callback.answer(text, show_alert=True)
            return

    await send(
        callback,
        order_service.order_text(order)
        + f"\n\nTelegram ID: {order['user_id']}"
        + (f"\nIzoh: {order['admin_note']}" if order.get("admin_note") else ""),
        admin_order_kb(order["id"]),
    )


# ==================================================================== to'lovlar
@router.callback_query(F.data == "adm:payments")
async def admin_payments(callback: CallbackQuery) -> None:
    payments = await db.list_pending_payments(20)
    text = "💳 TEKSHIRUVDAGI TO'LOVLAR\n\n" + (
        "\n".join(
            f"#{p['id']} | {p['user_id']} | {format_money(p['amount'])} | {p['method']}"
            for p in payments
        )
        if payments
        else "Tekshiruvdagi to'lov yo'q. ✅"
    )
    await send(callback, text, admin_payments_kb(payments))


@router.callback_query(F.data.startswith("adm:p:"))
async def admin_payment(callback: CallbackQuery, bot: Bot) -> None:
    parts = callback.data.split(":")
    if len(parts) not in (3, 4) or not parts[2].isdigit():
        await send(callback, t("invalid_input"))
        return

    payment = await db.get_payment(int(parts[2]))
    if payment is None:
        await send(callback, "To'lov topilmadi.", admin_back_kb("adm:payments"))
        return

    if len(parts) == 4:
        action = parts[3]
        if action == "ok":
            ok, text, user_id = await payment_service.approve(payment["id"], callback.from_user.id)
        elif action == "no":
            ok, text, user_id = await payment_service.reject(payment["id"], callback.from_user.id)
        else:
            await send(callback, t("invalid_input"))
            return

        if not ok:
            await callback.answer(text, show_alert=True)
            payment = await db.get_payment(payment["id"]) or payment
        else:
            log.info("To'lov %s: #%s (admin=%s)", action, payment["id"], callback.from_user.id)
            if user_id:
                await safe_send(
                    bot,
                    int(user_id),
                    ("✅ To'lov tasdiqlandi va balansga qo'shildi!" if action == "ok"
                     else "❌ To'lov rad etildi.\nSabab: chek noto'g'ri yoki takroriy.\nAdmin bilan bog'laning."),
                )
            await callback.answer(text, show_alert=True)
            payment = await db.get_payment(payment["id"]) or payment

    await send(callback, payment_service.payment_text(payment), admin_payment_kb(payment["id"]))


# ========================================================== balans boshqaruvi
@router.callback_query(F.data == "adm:bal")
async def admin_balance_ask(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.bal_user)
    await send(
        callback,
        "💰 BALANS BOSHQARUVI\n\n"
        "Foydalanuvchi Telegram ID raqamini yuboring.\n\n"
        "Bekor qilish: /cancel",
        back_reply_kb(),
    )


@router.callback_query(F.data.startswith("adm:baladd:"))
async def admin_balance_add(callback: CallbackQuery, state: FSMContext) -> None:
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit() or await db.get_user(int(raw_id)) is None:
        await send(callback, "Foydalanuvchi topilmadi.", admin_back_kb("adm:users"))
        return
    await state.set_state(AdminSG.bal_amount)
    await state.update_data(user_id=int(raw_id), sign=1)
    await send(callback, f"Qo'shiladigan summani yozing (so'mda), masalan 50000", back_reply_kb())


@router.callback_query(F.data.startswith("adm:balcut:"))
async def admin_balance_cut(callback: CallbackQuery, state: FSMContext) -> None:
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit() or await db.get_user(int(raw_id)) is None:
        await send(callback, "Foydalanuvchi topilmadi.", admin_back_kb("adm:users"))
        return
    await state.set_state(AdminSG.bal_amount)
    await state.update_data(user_id=int(raw_id), sign=-1)
    await send(callback, "Ayiriladigan summani yozing (so'mda), masalan 10000", back_reply_kb())


@router.message(AdminSG.bal_user, Command("cancel"))
async def admin_balance_cancel_user(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.bal_user)
async def admin_balance_user(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    target = parse_tg_id(message.text)
    user = await db.get_user(target) if target else None
    if user is None:
        await message.answer("❌ Bunday foydalanuvchi topilmadi. ID ni tekshiring:", reply_markup=back_reply_kb())
        return
    await state.set_state(AdminSG.bal_amount)
    await state.update_data(user_id=int(target), sign=1)
    await message.answer(
        f"✅ {target} topildi (balans: {format_money(user['balance'])}).\n\n"
        "Summani yozing. Ayirish uchun oldiga «-» qo'ying (masalan -5000).",
        reply_markup=back_reply_kb(),
    )


@router.message(AdminSG.bal_amount, Command("cancel"))
async def admin_balance_cancel_amount(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.bal_amount)
async def admin_balance_apply(message: Message, state: FSMContext, bot: Bot) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return

    data = await state.get_data()
    user_id = int(data.get("user_id") or 0)
    sign = -1 if str(message.text).strip().startswith("-") else 1
    raw = str(message.text).strip().replace(" ", "").replace("+", "").replace("-", "").replace(",", "")
    amount = parse_amount(raw, 1, 10**12)
    if amount is None or user_id <= 0:
        await message.answer("⚠️ To'g'ri summa kiriting (masalan 5000 yoki -5000).", reply_markup=back_reply_kb())
        return

    delta = sign * amount
    try:
        new_balance = await db.add_balance(
            user_id, delta, ttype="adjust", note="Admin tuzatish", allow_negative=True
        )
    except ValueError as exc:
        await message.answer(f"⚠️ {exc}", reply_markup=back_reply_kb())
        return

    await db.add_log(
        message.from_user.id,
        "balance",
        f"user={user_id} delta={delta} new={new_balance}",
    )
    await state.clear()
    log.info("Balans tuzatildi: user=%s %s → %s (admin=%s)", user_id, delta, new_balance, message.from_user.id)

    await message.answer(
        f"✅ Tayyor!\n\nFoydalanuvchi: {user_id}\nO'zgarish: {'+' if delta >= 0 else ''}{format_money(abs(delta))}\n"
        f"Yangi balans: {format_money(new_balance)}",
        reply_markup=admin_user_kb(user_id, False),
    )
    await safe_send(
        bot,
        user_id,
        f"💰 Hisobingiz to'ldirildi/yangilandi.\nO'zgarish: {'+' if delta >= 0 else ''}{format_money(abs(delta))}\n"
        f"Yangi balans: {format_money(new_balance)}",
    )


# ================================================================= mahsulotlar
from keyboards.inline import SETTING_ROWS  # noqa: E402


async def _products_text(ptype: str) -> str:
    products = await db.list_products(ptype, active_only=False)
    lines = [f"⚙️ {PTYPE_NAMES[ptype]} — mahsulotlar", ""]
    if not products:
        lines.append("Hozircha mahsulot yo'q.")
    for p in products:
        mark = "✅" if p["is_active"] else "❌"
        price = format_money(int(p["price"])) if int(p["price"]) > 0 else "⏳ narx yo'q"
        lines.append(f"{mark} #{p['id']} {p['name']} — {price}")
    lines += ["", "Boshqarish uchun mahsulotni tanlang yoki yangi qo'shing 👇"]
    return "\n".join(lines)


async def _product_detail_text(product: dict) -> str:
    price = format_money(int(product["price"])) if int(product["price"]) > 0 else "⏳ belgilanmagan"
    state = "✅ faol" if product["is_active"] else "❌ o'chirilgan"
    return (
        "⚙️ MAHSULOT\n\n"
        f"ID: #{product['id']}\n"
        f"Nomi: {product['name']}\n"
        f"Turi: {PTYPE_NAMES.get(product['ptype'], product['ptype'])}\n"
        f"Narx: {price}\n"
        f"Holat: {state}\n"
        f"Yaratilgan: {product['created_at']} UTC"
    )


async def _send_catalog(callback: CallbackQuery, ptype: str) -> None:
    products = await db.list_products(ptype, active_only=False)
    await send(callback, await _products_text(ptype), admin_products_kb(ptype, products))


@router.callback_query(F.data.startswith("adm:pr:"))
async def admin_products(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    # adm:pr:<ptype> | adm:pr:<ptype>:p<id> | adm:pr:<ptype>:p<id>:action
    if len(parts) < 3 or parts[2] not in PTYPE_NAMES:
        await send(callback, t("invalid_input"))
        return

    ptype = parts[2]
    if len(parts) == 3:
        await state.clear()
        await _send_catalog(callback, ptype)
        return

    pid_raw = parts[3]
    if not pid_raw.startswith("p") or not pid_raw[1:].isdigit():
        await send(callback, t("invalid_input"))
        return
    product = await db.get_product(int(pid_raw[1:]))
    if product is None or product["ptype"] != ptype:
        await send(callback, "Mahsulot topilmadi.", admin_back_kb(f"adm:pr:{ptype}"))
        return

    if len(parts) == 4:
        await state.clear()
        await send(callback, await _product_detail_text(product), admin_product_kb(ptype, product["id"], bool(product["is_active"])))
        return

    action = parts[4]
    if action == "toggle":
        new_active = not bool(product["is_active"])
        await db.update_product(product["id"], is_active=1 if new_active else 0)
        await db.add_log(callback.from_user.id, "product_toggle", f"#{product['id']} active={new_active}")
        log.info("Mahsulot holati: #%s → %s (admin=%s)", product["id"], new_active, callback.from_user.id)
        await _send_catalog(callback, ptype)
    elif action == "price":
        await state.set_state(AdminSG.price_edit)
        await state.update_data(product_id=product["id"], ptype=ptype)
        await send(
            callback,
            f"💲 «{product['name']}» uchun yangi narxni yozing (so'mda).\n"
            "Narxsiz qoldirish uchun 0 yozing.\n\nBekor qilish: /cancel",
            back_reply_kb(),
        )
    else:
        await send(callback, t("invalid_input"))


@router.message(AdminSG.price_edit, Command("cancel"))
async def admin_price_edit_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.price_edit)
async def admin_price_edit_apply(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    data = await state.get_data()
    price = parse_int(message.text, 0, 10**12)
    if price is None:
        await message.answer("⚠️ Faqat raqam kiriting (masalan 25000 yoki 0).", reply_markup=back_reply_kb())
        return
    await db.update_product(int(data["product_id"]), price=price)
    await db.add_log(message.from_user.id, "product_price", f"#{data['product_id']} → {price}")
    await state.clear()
    product = await db.get_product(int(data["product_id"]))
    await message.answer(
        f"✅ Narx saqlandi: {format_money(price)}",
        reply_markup=admin_product_kb(str(data["ptype"]), int(data["product_id"]), bool(product["is_active"]) if product else False),
    )


@router.callback_query(F.data.startswith("adm:new:"))
async def admin_new_product(callback: CallbackQuery, state: FSMContext) -> None:
    ptype = callback.data.split(":")[-1]
    if ptype not in PTYPE_NAMES:
        await send(callback, t("invalid_input"))
        return
    await state.set_state(AdminSG.prod_name)
    await state.update_data(ptype=ptype)
    await send(
        callback,
        f"➕ YANGI {PTYPE_NAMES[ptype].upper()} MAHSULOT\n\n"
        "Mahsulot nomini yozing.\n\nBekor qilish: /cancel",
        back_reply_kb(),
    )


@router.message(AdminSG.prod_name, Command("cancel"))
async def admin_prod_name_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.prod_name)
async def admin_prod_name(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    name = clean_line(message.text, 60)
    if not name:
        await message.answer("⚠️ Nomi bo'sh bo'lishi mumkin emas.", reply_markup=back_reply_kb())
        return
    data = await state.get_data()
    ptype = data.get("ptype")
    await state.update_data(name=name)
    if ptype == PTYPE_GIFT:
        await state.set_state(AdminSG.prod_image)
        await message.answer(
            f"🎁 «{name}» uchun rasm yuboring.\nRasm yo'q bo'lsa /skip yozing.",
            reply_markup=back_reply_kb(),
        )
        return
    await state.set_state(AdminSG.prod_price)
    await message.answer("💲 Narxni yozing (so'mda). 0 — narx hali belgilanmagan.", reply_markup=back_reply_kb())


@router.message(AdminSG.prod_image, Command("cancel"))
async def admin_prod_image_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.prod_image, Command("skip"))
async def admin_prod_image_skip(message: Message, state: FSMContext) -> None:
    await state.update_data(image=None)
    await state.set_state(AdminSG.prod_price)
    await message.answer("Rasm o'tkazildi. ➕ Narxni yozing (so'mda).", reply_markup=back_reply_kb())


@router.message(AdminSG.prod_image)
async def admin_prod_image(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text) or (message.text and message.text.strip().lower() == "/skip"):
        if message.text.strip().lower() == "/skip":
            await admin_prod_image_skip(message, state)
            return
        await show_main_menu(message, state)
        return
    if not message.photo:
        await message.answer("⚠️ Rasm yuboring yoki /skip yozing.", reply_markup=back_reply_kb())
        return
    await state.update_data(image=message.photo[-1].file_id)
    await state.set_state(AdminSG.prod_price)
    await message.answer("✅ Rasm qabul qilindi. ➕ Narxni yozing (so'mda).", reply_markup=back_reply_kb())


@router.message(AdminSG.prod_price, Command("cancel"))
async def admin_prod_price_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.prod_price)
async def admin_prod_price(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    price = parse_int(message.text, 0, 10**12)
    if price is None:
        await message.answer("⚠️ Faqat raqam kiriting (masalan 25000).", reply_markup=back_reply_kb())
        return

    data = await state.get_data()
    ptype = data.get("ptype")
    if ptype not in PTYPE_NAMES:
        await state.clear()
        await message.answer(t("error"), reply_markup=main_menu_keyboard())
        return

    product_id = await db.add_product(
        ptype=ptype,
        name=data.get("name", "—"),
        price=price,
        meta={"emoji": "🎁"} if ptype == PTYPE_GIFT else {},
        image_file_id=data.get("image"),
    )
    await db.add_log(message.from_user.id, "product_add", f"#{product_id} {ptype} {price}")
    await state.clear()
    log.info("Yangi mahsulot: #%s (%s, %s so'm, admin=%s)", product_id, ptype, price, message.from_user.id)
    await message.answer(
        f"✅ Mahsulot qo'shildi!\n\nID: #{product_id}\nNomi: {data.get('name')}\nNarx: {format_money(price)}",
        reply_markup=main_menu_keyboard(),
    )
    await message.answer(await _products_text(ptype), reply_markup=admin_products_kb(ptype, await db.list_products(ptype, active_only=False)))


# =================================================================== promo-kod
@router.callback_query(F.data == "adm:promo")
async def admin_promo_list(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    promos = await db.list_promos(20)
    text = "🎟 PROMO-KODLAR\n\n" + (
        "\n".join(
            f"{'✅' if p['is_active'] else '❌'} {p['code']} | +{format_money(p['bonus'])} | "
            f"foydalanildi: {p['used_count']}"
            + (f"/{p['max_uses']}" if int(p['max_uses']) else "")
            + (f" | muddat: {p['expires_at'][:10]}" if p['expires_at'] else "")
            for p in promos
        )
        if promos
        else "Hozircha promo-kod yo'q."
    )
    await send(callback, text, admin_promo_kb(promos))


@router.callback_query(F.data == "adm:pc:new")
async def admin_promo_new(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.promo_code)
    await send(callback, "Yangi promo-kodni yozing (3–32 belgi: harf, raqam, _ yoki -):", back_reply_kb())


@router.message(AdminSG.promo_code, Command("cancel"))
async def admin_promo_code_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.promo_code)
async def admin_promo_code(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    code = normalize_promo(message.text)
    if code is None:
        await message.answer("⚠️ Kod noto'g'ri. 3–32 belgi: harf, raqam, _ yoki -", reply_markup=back_reply_kb())
        return
    if await db.get_promo_by_code(code):
        await message.answer(f"⚠️ '{code}' kodi allaqachon mavjud.", reply_markup=back_reply_kb())
        return
    await state.update_data(code=code)
    await state.set_state(AdminSG.promo_bonus)
    await message.answer("💰 Bonus miqdorini yozing (so'mda), masalan 5000:", reply_markup=back_reply_kb())


@router.message(AdminSG.promo_bonus, Command("cancel"))
async def admin_promo_bonus_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.promo_bonus)
async def admin_promo_bonus(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    bonus = parse_amount(message.text, 1, 10**12)
    if bonus is None:
        await message.answer("⚠️ Musbat raqam kiriting (masalan 5000).", reply_markup=back_reply_kb())
        return
    await state.update_data(bonus=bonus)
    await state.set_state(AdminSG.promo_days)
    await message.answer(
        "📅 Amal qilish muddatini yozing (kunlarda).\n0 — cheksiz muddat.", reply_markup=back_reply_kb()
    )


@router.message(AdminSG.promo_days, Command("cancel"))
async def admin_promo_days_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.promo_days)
async def admin_promo_days(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    days = parse_int(message.text, 0, 3650)
    if days is None:
        await message.answer("⚠️ 0 dan 3650 gacha raqam kiriting.", reply_markup=back_reply_kb())
        return
    expires_at = None
    if days > 0:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    await state.update_data(expires_at=expires_at)
    await state.set_state(AdminSG.promo_uses)
    await message.answer(
        "🔢 Umumiy foydalanish limitini yozing.\n0 — cheksiz (kodni hamma ishlata oladi).",
        reply_markup=back_reply_kb(),
    )


@router.message(AdminSG.promo_uses, Command("cancel"))
async def admin_promo_uses_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.promo_uses)
async def admin_promo_uses(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    uses = parse_int(message.text, 0, 10**9)
    if uses is None:
        await message.answer("⚠️ 0 yoki musbat raqam kiriting.", reply_markup=back_reply_kb())
        return
    await state.update_data(max_uses=uses)
    await state.set_state(AdminSG.promo_per_user)
    await message.answer(
        "👤 Bir foydalanuvchi necha marta ishlata oladi?\n1 — bir marta (tavsiya etiladi).",
        reply_markup=back_reply_kb(),
    )


@router.message(AdminSG.promo_per_user, Command("cancel"))
async def admin_promo_per_user_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.promo_per_user)
async def admin_promo_create(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    per_user = parse_int(message.text, 1, 100)
    if per_user is None:
        await message.answer("⚠️ 1 dan 100 gacha raqam kiriting.", reply_markup=back_reply_kb())
        return

    data = await state.get_data()
    await state.clear()
    promo_id = await db.create_promo(
        code=data["code"],
        bonus=int(data["bonus"]),
        description="",
        expires_at=data.get("expires_at"),
        max_uses=int(data.get("max_uses") or 0),
        per_user_limit=per_user,
    )
    await db.add_log(message.from_user.id, "promo_create", f"{data['code']} +{data['bonus']}")
    log.info("Promo yaratildi: %s (admin=%s)", data["code"], message.from_user.id)

    expires = data.get("expires_at")
    await message.answer(
        "✅ PROMO-KOD YARATILDI!\n\n"
        f"Kod: {data['code']}\n"
        f"Bonus: {format_money(data['bonus'])}\n"
        f"Muddat: {expires[:10] if expires else 'cheksiz'}\n"
        f"Umumiy limit: {data.get('max_uses') or 'cheksiz'}\n"
        f"Bir foydalanuvchi uchun: {per_user} marta\n"
        f"ID: #{promo_id}",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("adm:pc:"))
async def admin_promo_item(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    if len(parts) not in (3, 4) or not parts[2].isdigit():
        await send(callback, t("invalid_input"))
        return
    promo = await db.get_promo(int(parts[2]))
    if promo is None:
        await send(callback, "Promo-kod topilmadi.", admin_back_kb("adm:promo"))
        return

    if len(parts) == 4:
        action = parts[3]
        if action == "toggle":
            new_active = not bool(promo["is_active"])
            await db.set_promo_active(promo["id"], new_active)
            await db.add_log(callback.from_user.id, "promo_toggle", f"{promo['code']} active={new_active}")
            promo = await db.get_promo(promo["id"]) or promo
        elif action == "del":
            await db.delete_promo(promo["id"])
            await db.add_log(callback.from_user.id, "promo_delete", promo["code"])
            log.info("Promo o'chirildi: %s (admin=%s)", promo["code"], callback.from_user.id)
            promos = await db.list_promos(20)
            await send(callback, f"🗑 «{promo['code']}» o'chirildi.", admin_promo_kb(promos))
            return
        else:
            await send(callback, t("invalid_input"))
            return

    used = await db.promo_usage_count(promo["id"])
    state_label = "✅ faol" if promo["is_active"] else "❌ o'chirilgan"
    text = (
        "🎟 PROMO-KOD\n\n"
        f"Kod: {promo['code']}\n"
        f"Bonus: {format_money(promo['bonus'])}\n"
        f"Muddat: {promo['expires_at'][:10] if promo['expires_at'] else 'cheksiz'}\n"
        f"Umumiy limit: {promo['max_uses'] or 'cheksiz'}\n"
        f"Ishlatilgan: {used} marta\n"
        f"Bir foydalanuvchi uchun: {promo['per_user_limit']}\n"
        f"Holat: {state_label}"
    )
    await send(callback, text, admin_promo_item_kb(promo["id"], bool(promo["is_active"])))


# ================================================================ referallar
@router.callback_query(F.data == "adm:refs")
async def admin_refs(callback: CallbackQuery) -> None:
    stats = await db.referral_stats()
    top = await db.fetchall(
        "SELECT referrer_id, COUNT(*) AS c FROM referrals WHERE status = 'active'"
        " GROUP BY referrer_id ORDER BY c DESC LIMIT 5"
    )
    lines = [
        "👥 REFERALLAR STATISTIKASI",
        "",
        f"Jami takliflar: {stats['total']}",
        f"Faol (bonus berilgan): {stats['active']}",
        f"Berilgan bonus: {format_money(stats['paid'])}",
    ]
    if top:
        lines += ["", "🏆 Eng faol taklif qiluvchilar:"]
        for row in top:
            lines.append(f"• {row['referrer_id']} — {row['c']} ta")
    await send(callback, "\n".join(lines), admin_back_kb())


# ============================================================ ommaviy xabar
@router.callback_query(F.data == "adm:bcast")
async def admin_bcast_ask(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.bcast)
    await send(
        callback,
        "📢 OMMaviy XABAR\n\n"
        "Barcha foydalanuvchilarga yuboriladigan matnni yoki rasmni yuboring.\n\n"
        "Bekor qilish: /cancel",
        back_reply_kb(),
    )


@router.message(AdminSG.bcast, Command("cancel"))
async def admin_bcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.bcast)
async def admin_bcast_preview(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    text = clean_text(message.text or message.caption or "", 4000)
    photo = message.photo[-1].file_id if message.photo else None
    if not text and not photo:
        await message.answer("⚠️ Matn yoki rasm yuboring.", reply_markup=back_reply_kb())
        return

    await state.set_data({"text": text, "photo": photo})
    await state.set_state(None)

    users = await db.count_users()
    kb = yes_no_kb("adm:bc:ok", "adm:bc:no", "✅ Yuborish", "❌ Bekor qilish")
    header = f"📢 PREVYU — {users} ta foydalanuvchiga yuboriladi:\n\n"
    if photo:
        await message.answer_photo(photo, caption=(header + text) if text else header.strip(), reply_markup=kb)
    else:
        await message.answer(header + text, reply_markup=kb)


@router.callback_query(F.data == "adm:bc:no")
async def admin_bcast_decline(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Bekor qilindi")
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass


@router.callback_query(F.data == "adm:bc:ok")
async def admin_bcast_run(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    text = data.get("text") or ""
    photo = data.get("photo")
    if not text and not photo:
        await state.clear()
        await callback.answer("Xabar topilmadi — qaytadan yuboring.", show_alert=True)
        return

    if _broadcast_lock.locked():
        await callback.answer("Boshqa xabar hali yuborilmoqda. Biroz kuting.", show_alert=True)
        return

    await state.clear()
    await callback.answer("Yuborish boshlandi...")

    async with _broadcast_lock:
        delay_ms = await db.get_int_setting("broadcast_delay_ms", 50)
        delay = max(10, min(1000, delay_ms)) / 1000
        sent = failed = 0
        for user_id in await db.list_user_ids():
            if photo:
                ok = await safe_send_photo(bot, user_id, photo, text or None)
            else:
                ok = await safe_send(bot, user_id, text)
            sent += 1 if ok else 0
            failed += 0 if ok else 1
            await asyncio.sleep(delay)

    await db.add_log(callback.from_user.id, "broadcast", f"sent={sent} failed={failed}")
    log.info("Ommaviy xabar yuborildi: %s ta (admin=%s)", sent, callback.from_user.id)
    await safe_send(
        bot,
        callback.from_user.id,
        f"✅ Ommaviy xabar yakunlandi.\nYuborildi: {sent}\nMuvaffaqiyatsiz: {failed}",
    )


# =================================================================== sozlamalar
async def _methods_text() -> str:
    methods = await payment_service.get_methods(include_inactive=True)
    lines = ["💳 TO'LOV USULLARI", ""]
    if not methods:
        lines.append("Hali usul qo'shilmagan. «➕ Yangi usul» tugmasini bosing.")
    for m in methods:
        mark = "✅" if m.get("active", True) else "❌"
        has_details = "rekvizit bor" if str(m.get("details") or "").strip() else "⚠️ rekvizit yo'q"
        lines.append(f"{mark} {m['name']} ({m['id']}) — {has_details}")
    lines += ["", "Faqat «✅» holatdagi usullar foydalanuvchilarga chiqadi."]
    return "\n".join(lines)


@router.callback_query(F.data == "adm:set")
async def admin_settings(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    values = await db.get_settings()
    lines = ["⚙️ BOT SOZLAMALARI", ""]
    for key, label, _ in SETTING_ROWS:
        raw = values.get(key, "")
        display = raw if raw not in ("", None) else "—"
        if key != "service_notice" and key in _INT_SETTINGS:
            try:
                display = f"{int(raw):,}".replace(",", " ") + (" so'm" if key not in ("custom_stars_min", "custom_stars_max", "broadcast_delay_ms") else "")
            except (TypeError, ValueError):
                display = raw or "—"
        lines.append(f"• {label}: {display}")
    lines += ["", "O'zgartirmoqchi bo'lgan sozlamani tanlang 👇"]
    await send(callback, "\n".join(lines), admin_settings_kb())


@router.callback_query(F.data.startswith("adm:edit:"))
async def admin_setting_ask(callback: CallbackQuery, state: FSMContext) -> None:
    key = callback.data.split(":")[-1]
    allowed = {k for k, _, _ in SETTING_ROWS}
    if key not in allowed:
        await send(callback, t("invalid_input"), admin_back_kb("adm:set"))
        return
    label = next((lbl for k, lbl, _ in SETTING_ROWS if k == key), key)
    current = await db.get_setting(key, "") or "—"
    hint = "Yangi qiymatni yozing." if key == "service_notice" else "Yangi qiymatni yozing (faqat raqam)."
    if key == "service_notice":
        hint = "E'lon matnini yozing (bo'sh qoldirish uchun: —)."
    await state.set_state(AdminSG.setting)
    await state.update_data(key=key)
    await send(callback, f"⚙️ {label}\n\nJoriy qiymat: {current}\n\n{hint}\n\nBekor qilish: /cancel", back_reply_kb())


@router.message(AdminSG.setting, Command("cancel"))
async def admin_setting_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.setting)
async def admin_setting_apply(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    data = await state.get_data()
    key = data.get("key")
    if key not in {k for k, _, _ in SETTING_ROWS}:
        await state.clear()
        await message.answer(t("error"), reply_markup=main_menu_keyboard())
        return

    if key in _INT_SETTINGS:
        value: object = parse_int(message.text, 0, 10**15)
        if value is None:
            await message.answer("⚠️ Faqat raqam kiriting.", reply_markup=back_reply_kb())
            return
    else:
        text = clean_text(message.text, 500)
        value = "" if text in ("—", "-") else text

    await db.set_setting(key, value)
    await db.add_log(message.from_user.id, "setting", f"{key} → {value}")
    log.info("Sozlama o'zgardi: %s = %s (admin=%s)", key, value, message.from_user.id)
    await state.clear()
    await message.answer(f"✅ Saqlandi.\n\n{key} = {value or '—'}", reply_markup=main_menu_keyboard())


# ============================================================== to'lov usullari
@router.callback_query(F.data == "adm:paym")
async def admin_methods(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send(callback, await _methods_text(), admin_methods_kb(await payment_service.get_methods(include_inactive=True)))


@router.callback_query(F.data == "adm:paym:new")
async def admin_method_new(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.method_name)
    await send(
        callback,
        "Yangi to'lov usuli nomini yozing\n(masalan: UzCard, Click, Payme):",
        back_reply_kb(),
    )


@router.message(AdminSG.method_name, Command("cancel"))
async def admin_method_name_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.method_name)
async def admin_method_name(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    name = clean_line(message.text, 50)
    if not name:
        await message.answer("⚠️ Nom bo'sh bo'lishi mumkin emas.", reply_markup=back_reply_kb())
        return
    method = await payment_service.add_method(name)
    await state.set_state(AdminSG.method_details)
    await state.update_data(method_id=method["id"])
    await db.add_log(message.from_user.id, "pay_method_add", name)
    await message.answer(
        f"✅ «{name}» qo'shildi.\n\n"
        "Endi to'lov rekvizitini/ko'rsatmasini yuboring:\n"
        "(masalan: Karta: 8600 xxx; Qabul qiluvchi: Ism Familiya)\n\n"
        "Rekvizitsiz qoldirish uchun /skip yozing.",
        reply_markup=back_reply_kb(),
    )


@router.message(AdminSG.method_details, Command("cancel"))
async def admin_method_details_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.method_details, Command("skip"))
async def admin_method_details_skip(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Rekvizit qoldirildi (bo'sh).", reply_markup=main_menu_keyboard())
    await message.answer(await _methods_text(), reply_markup=admin_methods_kb(await payment_service.get_methods(include_inactive=True)))


@router.message(AdminSG.method_details)
async def admin_method_details(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    data = await state.get_data()
    details = clean_text(message.text, 1500)
    await payment_service.update_method(str(data.get("method_id")), details=details)
    await db.add_log(message.from_user.id, "pay_method_details", str(data.get("method_id")))
    await state.clear()
    await message.answer("✅ Rekvizit saqlandi.", reply_markup=main_menu_keyboard())
    await message.answer(await _methods_text(), reply_markup=admin_methods_kb(await payment_service.get_methods(include_inactive=True)))


@router.message(AdminSG.method_edit, Command("cancel"))
async def admin_method_edit_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


@router.message(AdminSG.method_edit)
async def admin_method_edit_apply(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    data = await state.get_data()
    details = clean_text(message.text, 1500)
    await payment_service.update_method(str(data.get("method_id")), details=details)
    await db.add_log(message.from_user.id, "pay_method_edit", str(data.get("method_id")))
    await state.clear()
    await message.answer("✅ Rekvizit yangilandi.", reply_markup=main_menu_keyboard())
    await message.answer(await _methods_text(), reply_markup=admin_methods_kb(await payment_service.get_methods(include_inactive=True)))


@router.callback_query(F.data.startswith("adm:paym:"))
async def admin_method_item(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    if len(parts) == 3:
        method = await payment_service.get_method(parts[2])
        if method is None:
            await send(callback, "Usul topilmadi.", admin_back_kb("adm:paym"))
            return
        details = str(method.get("details") or "").strip() or "—"
        status = "✅ faol" if method.get("active", True) else "❌ o'chirilgan"
        await send(
            callback,
            f"💳 {method['name']}\n\nID: {method['id']}\nHolat: {status}\n\nRekvizit:\n{details}",
            admin_method_item_kb(method["id"]),
        )
        return

    if len(parts) != 4:
        await send(callback, t("invalid_input"))
        return
    method_id, action = parts[2], parts[3]

    if action == "toggle":
        method = await payment_service.get_method(method_id)
        if method is None:
            await send(callback, "Usul topilmadi.", admin_back_kb("adm:paym"))
            return
        new_active = not bool(method.get("active", True))
        await payment_service.update_method(method_id, active=new_active)
        await db.add_log(callback.from_user.id, "pay_method_toggle", f"{method_id} active={new_active}")
        await callback.answer("✅ Yoqildi" if new_active else "❌ O'chirildi", show_alert=True)
        await send(callback, await _methods_text(), admin_methods_kb(await payment_service.get_methods(include_inactive=True)))
    elif action == "del":
        ok = await payment_service.remove_method(method_id)
        await db.add_log(callback.from_user.id, "pay_method_delete", method_id)
        await callback.answer("O'chirildi" if ok else "Topilmadi", show_alert=True)
        await send(callback, await _methods_text(), admin_methods_kb(await payment_service.get_methods(include_inactive=True)))
    elif action == "edit":
        await state.set_state(AdminSG.method_edit)
        await state.update_data(method_id=method_id)
        await send(callback, "Yangi rekvizit matnini yuboring:", back_reply_kb())
    else:
        await send(callback, t("invalid_input"))


# ================================================================= admin jurnali
@router.callback_query(F.data == "adm:logs")
async def admin_logs(callback: CallbackQuery) -> None:
    logs = await db.recent_logs(15)
    text = "🧾 ADMIN JURNALI (oxirgi 15)\n\n" + (
        "\n".join(f"• {l['created_at']} | {l['admin_id']} | {l['action']} | {l['details']}" for l in logs)
        if logs
        else "Bo'sh."
    )
    await send(callback, text, admin_back_kb())


# ======================================================================= cancel
@router.message(Command("cancel"))
async def admin_cancel_any(message: Message, state: FSMContext) -> None:
    """Istalgan holatda /cancel — barcha FSM jarayonini to'xtatadi."""
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=main_menu_keyboard())


__all__ = ["router", "AdminSG"]
