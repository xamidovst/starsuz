"""👥 Referal tizimi: shaxsiy havola va statistika."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.inline import back_kb, menu_kb
from keyboards.main_menu import main_menu_keyboard
from services import referral_service
from utils.helpers import send
from utils.i18n import t
from utils.logger import get_logger
from utils.validators import format_money

log = get_logger("referral")
router = Router()


def _referral_text(user_id: int, stats: dict, link: str) -> str:
    return (
        "👥 REFERAL TIZIMI\n\n"
        "Do'stlaringizni taklif qiling va bonus oling!\n\n"
        f"🎯 Bonus (1 do'st uchun): {format_money(stats['bonus'])}\n"
        f"👥 Taklif qilinganlar: {stats['invited']}\n"
        f"✅ Faol (birinchi buyurtma bergan): {stats['active']}\n"
        f"💰 Umumiy bonus: {format_money(stats['earned'])}\n\n"
        "🔗 Shaxsiy havolangiz:\n"
        f"{link}\n\n"
        "Qoidalar:\n"
        "• O'zini o'zi taklif qilib bo'lmaydi.\n"
        "• Bonus taklif qilingan odam birinchi buyurtma berganda beriladi.\n"
        "• Takroriy yoki soxta hisoblar aniqlansa — bonus bekor qilinadi.\n"
        "• Taklif qilingan odam o'z havolasini boshqaga yuborsa — hisobga olinmaydi."
    )


@router.message(F.text == t("btn_referral"))
@router.message(Command("referral"))
async def referral_menu_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    stats = await referral_service.user_stats(message.from_user.id)
    link = referral_service.referral_link(message.from_user.id)
    await message.answer(_referral_text(message.from_user.id, stats, link), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "ref")
async def referral_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    stats = await referral_service.user_stats(callback.from_user.id)
    link = referral_service.referral_link(callback.from_user.id)
    await send(callback, _referral_text(callback.from_user.id, stats, link), menu_kb())


__all__ = ["router"]
