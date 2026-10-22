"""👤 Kabinet: shaxsiy ma'lumotlar, balans va statistika."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import db
from services import referral_service
from utils.helpers import send
from utils.i18n import t
from utils.logger import get_logger
from utils.validators import format_money

log = get_logger("profile")
router = Router()


def _kb():
    b = InlineKeyboardBuilder()
    b.button(text="💳 Hisobni to'ldirish", callback_data="topup")
    b.button(text="📦 Buyurtmalarim", callback_data="myorders")
    b.button(text="🎟 Promo-kod", callback_data="promo")
    b.button(text="👥 Referallar", callback_data="ref")
    b.button(text="🏠 Asosiy menyu", callback_data="menu")
    b.adjust(2, 2, 1)
    return b.as_markup()


async def cabinet_text(user_id: int) -> str:
    user = await db.get_user(user_id)
    if user is None:
        return "Hisobingiz topilmadi. /start bosing."

    stats = await referral_service.user_stats(user_id)
    orders_count = await db.count_orders(user_id=user_id)
    transactions = await db.list_user_transactions(user_id, limit=5)

    name = user.get("full_name") or "—"
    username = f"@{user['username']}" if user.get("username") else "—"

    lines = [
        "👤 KABINET",
        "",
        f"Ism: {name}",
        f"Username: {username}",
        f"Telegram ID: {user['telegram_id']}",
        f"Ro'yxatdan o'tgan: {user['created_at']} UTC",
        "",
        f"💰 Joriy balans: {format_money(int(user.get('balance') or 0))}",
        f"👥 Taklif qilingan do'stlar: {stats['invited']}",
        f"📦 Buyurtmalar soni: {orders_count}",
        f"🎟 Promo orqali bonus: {format_money(int(user.get('promo_bonus_total') or 0))}",
        f"🤝 Referal bonus: {format_money(int(user.get('referral_bonus_total') or 0))}",
    ]

    if int(user.get("is_banned") or 0):
        lines.append("⛔ Hisobingiz cheklangan.")

    if transactions:
        lines += ["", "🕓 Oxirgi amallar:"]
        labels = {
            "topup": "To'ldirish",
            "purchase": "Xarid",
            "refund": "Qaytarildi",
            "bonus": "Bonus",
            "promo": "Promo",
            "adjust": "Tuzatish",
        }
        for tx in transactions:
            sign = "+" if int(tx["amount"]) >= 0 else "−"
            amount = format_money(abs(int(tx["amount"])))
            kind = labels.get(tx["ttype"], tx["ttype"])
            lines.append(f"• {kind}: {sign}{amount}")

    return "\n".join(lines)


@router.message(F.text == t("btn_kabinet"))
@router.message(Command("cabinet"))
async def cabinet_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(await cabinet_text(message.from_user.id), reply_markup=_kb())


@router.callback_query(F.data == "cabinet")
async def cabinet_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send(callback, await cabinet_text(callback.from_user.id), _kb())


__all__ = ["router", "cabinet_text"]
