"""Asosiy (Reply) menyu klaviaturasi."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from utils.i18n import menu_texts, t

# Menyu tartibi — spetsifikatsiyadagidek
MAIN_MENU_KEYS: tuple[str, ...] = (
    "btn_stars",
    "btn_premium",
    "btn_gifts",
    "btn_kabinet",
    "btn_topup",
    "btn_promo",
    "btn_referral",
    "btn_orders",
    "btn_guide",
    "btn_partner",
    "btn_help",
)


def main_menu_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Ikki ustunli asosiy menyu (oxirgi tugma yakkacha)."""
    builder = ReplyKeyboardBuilder()
    labels = [t(key, lang) for key in MAIN_MENU_KEYS]

    i = 0
    while i + 1 < len(labels):
        builder.button(text=labels[i])
        builder.button(text=labels[i + 1])
        i += 2
    if i < len(labels):
        builder.button(text=labels[i])

    # 11 tugma: 2 2 2 2 2 1
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder=t("choose", lang),
        is_persistent=True,
    )


def back_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """«Orqaga» tugmasi bitta qatorda."""
    builder = ReplyKeyboardBuilder()
    builder.button(text=t("btn_back", lang))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def main_menu_text(lang: str = "uz") -> frozenset[str]:
    """Menyu tugmalarining matnlari (FSM da tekshirish uchun)."""
    return menu_texts(lang)


def is_menu_text(text: str | None, lang: str = "uz") -> bool:
    if not text:
        return False
    return text.strip() in menu_texts(lang)


def make_keyboard(rows: list[list[str]], lang: str = "uz") -> ReplyKeyboardMarkup:
    """Matn qatorlaridan oddiy ReplyKeyboard yasash (yordam, orqaga)."""
    builder = ReplyKeyboardBuilder()
    for row in rows:
        builder.button(text=row[0])
        if len(row) > 1:
            for label in row[1:]:
                builder.button(text=label)
    if rows:
        builder.adjust(*[len(r) for r in rows])
    return builder.as_markup(resize_keyboard=True)


__all__ = [
    "MAIN_MENU_KEYS",
    "main_menu_keyboard",
    "back_keyboard",
    "main_menu_text",
    "is_menu_text",
    "make_keyboard",
    "KeyboardButton",
    "ReplyKeyboardMarkup",
]
