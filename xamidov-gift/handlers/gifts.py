"""🎁 Telegram sovg'alar katalogi."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import PTYPE_GIFT, db
from services import order_service
from utils.helpers import send
from utils.i18n import t
from utils.logger import get_logger

log = get_logger("gifts")
router = Router()


@router.message(F.text == t("btn_gifts"))
async def menu_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await order_service.open_catalog(message, PTYPE_GIFT)


@router.callback_query(F.data == "gifts")
async def menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await order_service.open_catalog(callback, PTYPE_GIFT)


@router.callback_query(F.data.startswith("gifts:buy:"))
async def product_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return
    await order_service.open_product(callback, PTYPE_GIFT, int(raw_id))


@router.callback_query(F.data.startswith("gifts:order:"))
async def order_callback(callback: CallbackQuery, bot: Bot) -> None:
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return

    product = await db.get_product(int(raw_id))
    if product is None or product["ptype"] != PTYPE_GIFT or not int(product["is_active"]):
        await send(callback, "Mahsulot topilmadi yoki o'chirilgan.")
        return
    price = int(product["price"] or 0)
    if price <= 0:
        await send(callback, "⏳ Bu sovg'aning narxi hali belgilanmagan.\nAdmin tez orada belgilaydi.")
        return

    meta = order_service.product_meta(product)
    details = {"gift": product["name"], "emoji": meta.get("emoji", "🎁"), "target_user_id": callback.from_user.id}
    await order_service.place_order(
        callback,
        bot,
        PTYPE_GIFT,
        product["name"],
        price,
        product_id=product["id"],
        details=details,
    )


__all__ = ["router"]
