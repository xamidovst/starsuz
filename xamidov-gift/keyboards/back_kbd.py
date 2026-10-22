"""«Orqaga» tugmasi uchun yengil ReplyKeyboard (FSM davomida ishlatiladi)."""

from __future__ import annotations

from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from utils.i18n import t


def back_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Faqat «🔙 Orqaga» tugmasi — FSM savollarida chiqadi."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=t("btn_back", lang))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True, is_persistent=True)


__all__ = ["back_reply_kb"]
