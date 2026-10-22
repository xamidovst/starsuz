"""💎 Telegram Premium bo'limi (1/3/6/12 oylik tariflar)."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import PTYPE_PREMIUM, db
from services import order_service
from utils.helpers import send
from utils.i18n import t
from utils.logger import get_logger

log = get_logger("premium")
router = Router()


@router.message(F.text == t("btn_premium"))
async def menu_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await order_service.open_catalog(message, PTYPE_PREMIUM)


@router.callback_query(F.data == "premium")
async def menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await order_service.open_catalog(callback, PTYPE_PREMIUM)


@router.callback_query(F.data.startswith("premium:buy:"))
async def product_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return
    await order_service.open_product(callback, PTYPE_PREMIUM, int(raw_id))


@router.callback_query(F.data.startswith("premium:order:"))
async def order_callback(callback: CallbackQuery, bot: Bot) -> None:
    raw_id = callback.data.split(":")[-1]
    if not raw_id.isdigit():
        await send(callback, t("invalid_input"))
        return

    product = await db.get_product(int(raw_id))
    if product is None or product["ptype"] != PTYPE_PREMIUM or not int(product["is_active"]):
        await send(callback, "Mahsulot topilmadi yoki o'chirilgan.")
        return
    price = int(product["price"] or 0)
    if price <= 0:
        await send(callback, "⏳ Bu tarifning narxi hali belgilanmagan.\nAdmin tez orada belgilaydi.")
        return

    meta = order_service.product_meta(product)
    details = {"days": meta.get("days"), "target_user_id": callback.from_user.id}
    await order_service.place_order(
        callback,
        bot,
        PTYPE_PREMIUM,
        product["name"],
        price,
        product_id=product["id"],
        details=details,
    )
    log.info("Premium buyurtma: user=%s, %s", callback.from_user.id, product["name"])


__all__ = ["router"]
