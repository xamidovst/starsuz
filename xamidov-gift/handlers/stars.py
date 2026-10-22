"""⭐ Telegram Stars bo'limi (standart paketlar + maxsus miqdor)."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import PTYPE_STARS, db
from handlers.start import show_main_menu
from keyboards.back_kbd import back_reply_kb
from keyboards.main_menu import is_menu_text, main_menu_keyboard
from services import order_service
from utils.helpers import send
from utils.i18n import t
from utils.logger import get_logger
from utils.validators import format_money, parse_amount

log = get_logger("stars")
router = Router()


class StarsSG(StatesGroup):
    custom = State()


async def _limits() -> tuple[int, int]:
    minimum = await db.get_int_setting("custom_stars_min", 10)
    maximum = await db.get_int_setting("custom_stars_max", 100000)
    return max(minimum, 1), max(maximum, minimum)


@router.message(F.text == t("btn_stars"))
async def menu_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await order_service.open_catalog(message, PTYPE_STARS)


@router.callback_query(F.data == "stars")
async def menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await order_service.open_catalog(callback, PTYPE_STARS)


@router.callback_query(F.data.startswith("stars:buy:"))
async def product_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return
    await order_service.open_product(callback, PTYPE_STARS, int(raw_id))


@router.callback_query(F.data.startswith("stars:order:"))
async def order_callback(callback: CallbackQuery, bot: Bot) -> None:
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return
    product = await db.get_product(int(raw_id))
    if product is None or product["ptype"] != PTYPE_STARS or not int(product["is_active"]):
        await send(callback, "Mahsulot topilmadi yoki o'chirilgan.")
        return
    price = int(product["price"] or 0)
    if price <= 0:
        await send(callback, "⏳ Bu mahsulotning narxi hali belgilanmagan.\nAdmin tez orada belgilaydi.")
        return

    details = {"stars": order_service.product_meta(product).get("stars")}
    await order_service.place_order(
        callback,
        bot,
        PTYPE_STARS,
        product["name"],
        price,
        product_id=product["id"],
        details=details,
    )


# ------------------------------------------------------------ maxsus miqdor
@router.callback_query(F.data == "stars:custom")
async def ask_custom(callback: CallbackQuery, state: FSMContext) -> None:
    minimum, maximum = await _limits()
    unit = await db.get_int_setting("stars_unit_price", 0)
    price_line = f"1 ⭐ = {format_money(unit)}" if unit > 0 else "⏳ Narx hali belgilanmagan"
    await state.set_state(StarsSG.custom)
    await send(
        callback,
        "✍️ MAXSUS MIQDOR\n\n"
        f"Qancha Stars xohlaysiz?\n"
        f"Chegara: {minimum} — {maximum}\n"
        f"{price_line}\n\n"
        "Raqam yuboring yoki 🔙 Orqaga bosing.",
        back_reply_kb(),
    )


@router.message(StarsSG.custom)
async def custom_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return

    minimum, maximum = await _limits()
    amount = parse_amount(message.text, minimum, maximum)
    if amount is None:
        await message.answer(
            f"⚠️ {minimum} dan {maximum} gacha butun raqam kiriting.",
            reply_markup=back_reply_kb(),
        )
        return

    unit = await db.get_int_setting("stars_unit_price", 0)
    if unit <= 0:
        await state.clear()
        await message.answer(
            "⏳ Maxsus Stars narxi hali belgilanmagan.\nAdmin tomonidan belgilangach, buyurtma bera olasiz.",
            reply_markup=main_menu_keyboard(),
        )
        return

    price = amount * unit
    await state.clear()
    await order_service.place_order(
        message,
        bot,
        PTYPE_STARS,
        f"{amount} Stars (maxsus)",
        price,
        product_id=None,
        details={"stars": amount, "custom": True},
    )


__all__ = ["router", "StarsSG"]
