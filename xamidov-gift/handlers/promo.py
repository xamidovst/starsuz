"""🎟 Promo-kodlar: foydalanuvchi kiritadi, admin boshqaradi (admin.py ichida)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot
from aiogram.types import CallbackQuery, Message

from database import db
from handlers.start import show_main_menu
from keyboards.back_kbd import back_reply_kb
from keyboards.inline import back_kb
from keyboards.main_menu import is_menu_text, main_menu_keyboard
from utils.helpers import notify_admins, send
from utils.i18n import t
from utils.logger import get_logger
from utils.validators import format_money, normalize_promo

log = get_logger("promo")
router = Router()


class PromoSG(StatesGroup):
    code = State()


async def _ask_code(event) -> None:
    await send(
        event,
        "🎟 PROMO-KOD\n\n"
        "Promo-kodni yuboring (katta-kichik harflar farq qilmaydi).\n\n"
        "Bekor qilish uchun 🔙 Orqaga bosing.",
        back_reply_kb(),
    )


@router.message(F.text == t("btn_promo"))
@router.message(Command("promo"))
async def promo_menu_message(message: Message, state: FSMContext) -> None:
    await state.set_state(PromoSG.code)
    await _ask_code(message)


@router.callback_query(F.data == "promo")
async def promo_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PromoSG.code)
    await _ask_code(callback)


@router.message(PromoSG.code)
async def promo_input(message: Message, state: FSMContext, bot: Bot) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return

    code = normalize_promo(message.text)
    if code is None:
        await message.answer(
            "⚠️ Promo-kod 3–32 ta belgidan iborat bo'lishi kerak (harflar, raqamlar, _ yoki -).",
            reply_markup=back_reply_kb(),
        )
        return

    ok, bonus, msg = await db.use_promo(code, message.from_user.id)
    await state.clear()

    if not ok:
        await message.answer(f"❌ {msg}", reply_markup=main_menu_keyboard())
        log.info("Promo rad etildi: %s (user=%s, %s)", code, message.from_user.id, msg)
        return

    user = await db.get_user(message.from_user.id) or {}
    await message.answer(
        "🎉 PROMO-KOD QABUL QILINDI!\n\n"
        f"Kod: {code}\n"
        f"Bonus: {format_money(bonus)}\n"
        f"Yangi balans: {format_money(int(user.get('balance') or 0))}",
        reply_markup=main_menu_keyboard(),
    )
    await notify_admins(
        bot,
        "🎟 PROMO ISHLATILDI\n"
        f"Foydalanuvchi: {message.from_user.id}\n"
        f"Kod: {code}\n"
        f"Bonus: {format_money(bonus)}",
    )
    log.info("Promo ishlatildi: %s (user=%s, +%s)", code, message.from_user.id, bonus)


__all__ = ["router", "PromoSG"]
