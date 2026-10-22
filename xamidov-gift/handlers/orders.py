"""📦 Buyurtmalarim: ro'yxat, to'lash, bekor qilish."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import db
from keyboards.inline import back_kb, menu_kb, order_actions_kb, orders_list_kb
from keyboards.main_menu import main_menu_keyboard
from services import order_service
from utils.helpers import notify_admins, send
from utils.i18n import t
from utils.logger import get_logger
from utils.validators import format_money

log = get_logger("orders")
router = Router()


async def _orders_text(user_id: int) -> str:
    orders = await db.list_user_orders(user_id)
    if not orders:
        return "📦 Sizda hozircha buyurtma yo'q.\n\n⭐ Stars, 💎 Premium yoki 🎁 sovg'a bo'limidan buyurtma bering."
    return "📦 SIZNING BUYURTMALARINGIZ\n\n(Soningiz: {})\n\nBatafsil uchun buyurtmani tanlang 👇".format(len(orders))


@router.message(F.text == t("btn_orders"))
@router.message(Command("orders"))
async def orders_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    orders = await db.list_user_orders(message.from_user.id)
    if not orders:
        await message.answer(await _orders_text(message.from_user.id), reply_markup=main_menu_keyboard())
        return
    await message.answer(await _orders_text(message.from_user.id), reply_markup=orders_list_kb(orders))


@router.callback_query(F.data == "myorders")
async def orders_menu_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    orders = await db.list_user_orders(callback.from_user.id)
    if not orders:
        await send(callback, await _orders_text(callback.from_user.id), back_kb())
        return
    await send(callback, await _orders_text(callback.from_user.id), orders_list_kb(orders))


@router.callback_query(F.data.startswith("order:"))
async def order_detail(callback: CallbackQuery) -> None:
    order_no = callback.data.split(":")[-1]
    try:
        order = await order_service.get_owned_order(order_no, callback.from_user.id)
    except order_service.OrderError as exc:
        await send(callback, str(exc), back_kb("myorders"))
        return

    kb = order_actions_kb(order["order_no"]) if order["status"] == "awaiting_payment" else back_kb("myorders")
    await send(callback, order_service.order_text(order), kb)


@router.callback_query(F.data.startswith("pay:"))
async def pay_order(callback: CallbackQuery, bot: Bot) -> None:
    order_no = callback.data.split(":")[-1]
    ok, order, text = await order_service.pay_with_balance(order_no, callback.from_user.id)
    kb = back_kb("myorders")
    if ok and order:
        kb = order_actions_kb(order["order_no"]) if order["status"] == "awaiting_payment" else back_kb("myorders")
        await notify_admins(
            bot,
            "💳 BUYURTMA TO'LANDI\n"
            f"Raqam: {order['order_no']}\n"
            f"Foydalanuvchi: {order['user_id']}\n"
            f"Mahsulot: {order['product_name']}\n"
            f"Summa: {format_money(order['amount'])}\n"
            "Holat: 🕓 Kutilmoqda (bajarish kerak)",
        )
        log.info("Buyurtma to'landi: %s", order["order_no"])
    await send(callback, text, kb)


@router.callback_query(F.data.startswith("cancel:"))
async def cancel_order(callback: CallbackQuery) -> None:
    order_no = callback.data.split(":")[-1]
    ok, order, text = await order_service.cancel_order(order_no, callback.from_user.id)
    if ok:
        log.info("Buyurtma bekor qilindi: %s (user=%s)", order_no, callback.from_user.id)
    await send(callback, text, menu_kb())


__all__ = ["router"]
