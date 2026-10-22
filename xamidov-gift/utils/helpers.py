"""Umumiy yordamchi funksiyalar: javob yuborish va adminlarga xabar."""

from __future__ import annotations

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from config import ADMIN_IDS
from utils.logger import get_logger

log = get_logger("notify")


async def send(event, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    """Message yoki CallbackQuery uchun bir xil javob.

    CallbackQuery bo'lsa — tugma bildirishnomasini yopib, yangi xabar yuboradi
    (edit xatosiz, ishonchli ishlaydi).
    """
    if isinstance(event, CallbackQuery):
        try:
            await event.answer()
        except TelegramAPIError:
            pass
        target = event.message
        if isinstance(target, Message):
            await target.answer(text, reply_markup=kb)
        return
    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb)


async def safe_send(
    bot: Bot,
    chat_id: int,
    text: str,
    kb: InlineKeyboardMarkup | None = None,
) -> bool:
    """Xatolikka qaramay xabar yuborish (bloklangan foydalanuvchilar uchun)."""
    try:
        await bot.send_message(chat_id, text, reply_markup=kb)
        return True
    except TelegramAPIError as exc:
        log.info("Xabar yuborilmadi (chat=%s): %s", chat_id, type(exc).__name__)
        return False


async def safe_send_photo(
    bot: Bot,
    chat_id: int,
    photo: str,
    caption: str | None = None,
    kb: InlineKeyboardMarkup | None = None,
) -> bool:
    """Rasm yuborish (xatoliklarga qarshi himoyalangan)."""
    try:
        await bot.send_photo(chat_id, photo, caption=caption or None, reply_markup=kb)
        return True
    except TelegramAPIError:
        log.info("Rasm yuborilmadi (chat=%s)", chat_id)
        return False


async def notify_admins(
    bot: Bot,
    text: str,
    kb: InlineKeyboardMarkup | None = None,
) -> int:
    """Barcha adminlarga xabar yuboradi. Yuborilganlar sonini qaytaradi."""
    sent = 0
    for admin_id in sorted(ADMIN_IDS):
        if await safe_send(bot, admin_id, text, kb):
            sent += 1
    return sent


def admin_ids() -> frozenset[int]:
    return ADMIN_IDS


def is_admin(user_id: int | None) -> bool:
    return bool(user_id) and int(user_id) in ADMIN_IDS


async def admin_filter(event) -> bool:
    """aiogram filtri: faqat adminlar uchun (Message yoki CallbackQuery)."""
    user = getattr(event, "from_user", None)
    return is_admin(user.id if user else None)
