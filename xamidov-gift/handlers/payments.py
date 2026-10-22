"""💳 Hisobni to'ldirish: chek yuborish, admin tasdiqlashi va Telegram Stars invoice."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from database import db
from handlers.start import show_main_menu
from keyboards.back_kbd import back_reply_kb
from keyboards.inline import back_kb, topup_amount_kb, topup_methods_kb, topup_stars_kb
from keyboards.main_menu import is_menu_text, main_menu_keyboard
from services import payment_service
from utils.helpers import notify_admins, send
from utils.i18n import t
from utils.logger import get_logger
from utils.validators import format_money, parse_amount

log = get_logger("topup")
router = Router()


class TopUpSG(StatesGroup):
    amount = State()
    receipt = State()


# ------------------------------------------------------------------- menyu
async def _topup_text(user_id: int) -> str:
    user = await db.get_user(user_id) or {}
    methods = await payment_service.get_methods()
    rate = await payment_service.stars_rate()
    minimum = await db.get_int_setting("min_topup", 0)

    lines = [
        "💳 HISOBNI TO'LDIRISH",
        "",
        f"💰 Joriy balans: {format_money(int(user.get('balance') or 0))}",
        "",
        "To'lov usulini tanlang:",
    ]
    if not methods:
        lines.append("• Hozircha karta/terminal usullari mavjud emas (admin tomonidan qo'shiladi).")
    lines += [
        "",
        "⭐ Telegram Stars orqali to'ldirish ham mavjud:",
        f"   1 ⭐ = {format_money(rate)}" if rate > 0 else "   ⏳ Kurs hali belgilanmagan",
        "",
        f"⬇️ Minimal summa: {format_money(minimum)}" if minimum > 0 else "",
        "",
        "Chekni (rasm/hujjat) yuboring — admin tasdiqlaydi.",
    ]
    return "\n".join(line for line in lines if line is not None)


@router.message(F.text == t("btn_topup"))
@router.message(Command("topup"))
async def topup_menu_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    methods = await payment_service.get_methods()
    await message.answer(await _topup_text(message.from_user.id), reply_markup=topup_methods_kb(methods))


@router.callback_query(F.data == "topup")
async def topup_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    methods = await payment_service.get_methods()
    await send(callback, await _topup_text(callback.from_user.id), topup_methods_kb(methods))


# ------------------------------------------------------------- usul tanlash
@router.callback_query(F.data.startswith("topup:"))
async def choose_method(callback: CallbackQuery, state: FSMContext) -> None:
    method_id = callback.data.split(":")[-1]

    if method_id == "stars":
        presets = await payment_service.stars_presets()
        rate = await payment_service.stars_rate()
        text = (
            "⭐ TELEGRAM STARS ORQALI TO'LDIRISH\n\n"
            "Telegram'ning rasmiy to'lov tizimidan foydalaniladi.\n"
            + (f"Har bir yulduzga {format_money(rate)} hisoblanadi.\n" if rate > 0 else "⏳ Kurs hali belgilanmagan.\n")
            + "\nTo'plamni tanlang 👇"
        )
        await send(callback, text, topup_stars_kb(presets))
        return

    method = await payment_service.get_method(method_id)
    if method is None:
        await send(callback, "To'lov usuli topilmadi.", back_kb("topup"))
        return

    details = str(method.get("details") or "").strip()
    text = f"💳 {method['name']}\n\n"
    if details:
        text += f"To'lov ma'lumotlari:\n{details}\n\n"
    else:
        text += "⚠️ Rekvizit hali kiritilmagan — admin bilan bog'laning.\n\n"
    minimum = await db.get_int_setting("min_topup", 0)
    maximum = await db.get_int_setting("max_topup", 0)
    text += "To'lov summasini tanlang yoki kiriting (so'mda):"
    if minimum > 0:
        text += f"\nChegara: {format_money(minimum)}" + (f" — {format_money(maximum)}" if maximum > 0 else "")

    await state.set_data({"method": method["id"], "method_name": method["name"]})
    await send(callback, text, topup_amount_kb(minimum))


# ------------------------------------------------------------------ summa
@router.callback_query(F.data.startswith("topamount:"))
async def choose_amount(callback: CallbackQuery, state: FSMContext) -> None:
    raw = callback.data.split(":")[-1]
    data = await state.get_data()
    if not data.get("method"):
        await send(callback, "Avval to'lov usulini tanlang.", back_kb("topup"))
        await state.clear()
        return

    if raw == "custom":
        minimum = await db.get_int_setting("min_topup", 1)
        await state.set_state(TopUpSG.amount)
        await send(
            callback,
            f"✏️ To'lov summasini yozing (so'mda).\nMinimal: {format_money(minimum)}",
            back_reply_kb(),
        )
        return

    if not raw.isdigit():
        await send(callback, t("invalid_input"), back_kb("topup"))
        return
    await _start_receipt_stage(callback, int(raw), state)


async def _start_receipt_stage(event, amount: int, state: FSMContext) -> None:
    """Summa tasdiqlandi — to'lov yaratib, chek so'raymiz."""
    minimum = await db.get_int_setting("min_topup", 0)
    maximum = await db.get_int_setting("max_topup", 0)
    if amount <= 0 or (minimum and amount < minimum) or (maximum and amount > maximum):
        await send(
            event,
            f"⚠️ Noto'g'ri summa."
            + (f" Minimal {format_money(minimum)}." if minimum else "")
            + (f" Maksimal {format_money(maximum)}." if maximum else ""),
            back_kb("topup"),
        )
        return

    data = await state.get_data()
    method_name = data.get("method_name") or "—"
    user = getattr(event, "from_user", None)
    payment_id = await payment_service.create_topup_request(user.id, method_name, amount)
    if payment_id is None:
        await send(event, t("error"), back_kb("topup"))
        return

    await state.set_state(TopUpSG.receipt)
    await state.update_data(payment_id=payment_id, amount=amount)
    await send(
        event,
        "📤 CHEK YUBORING\n\n"
        f"Summa: {format_money(amount)}\n"
        f"Usul: {method_name}\n\n"
        "To'lov chekining RASMIni, PDF hujjatini yoki matnini yuboring.\n"
        "Admin tasdiqlagach, balans bir marta oshiriladi.\n\n"
        "Bekor qilish uchun 🔙 Orqaga bosing.",
        back_reply_kb(),
    )


@router.message(TopUpSG.amount)
async def input_amount(message: Message, state: FSMContext) -> None:
    if is_menu_text(message.text):
        await show_main_menu(message, state)
        return
    data = await state.get_data()
    if not data.get("method"):
        await state.clear()
        await show_main_menu(message, state)
        return
    amount = parse_amount(
        message.text,
        await db.get_int_setting("min_topup", 1),
        await db.get_int_setting("max_topup", 10**15),
    )
    if amount is None:
        await message.answer("⚠️ To'g'ri summa kiriting (so'mda).", reply_markup=back_reply_kb())
        return
    await _start_receipt_stage(message, amount, state)


# ------------------------------------------------------------------- chek
@router.message(TopUpSG.receipt, F.photo | F.document | F.text)
async def input_receipt(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and is_menu_text(message.text):
        await show_main_menu(message, state)
        return

    data = await state.get_data()
    payment_id = data.get("payment_id")
    if not payment_id:
        await state.clear()
        await show_main_menu(message, state)
        return

    receipt = payment_service.receipt_from_message(message)
    if receipt is None:
        await message.answer(
            "⚠️ Chek sifatida rasm, PDF hujjat yoki matn yuboring.",
            reply_markup=back_reply_kb(),
        )
        return

    key, ref = receipt
    error = await payment_service.submit_receipt(int(payment_id), key, ref)
    if error:
        await message.answer(f"⚠️ {error}\n\nBoshqa chek yuboring yoki 🔙 Orqaga bosing.", reply_markup=back_reply_kb())
        return

    payment = await db.get_payment(int(payment_id))
    amount = int(payment["amount"]) if payment else int(data.get("amount") or 0)
    method_name = payment["method"] if payment else "—"

    await state.clear()
    await message.answer(
        "✅ Chek qabul qilindi!\n\n"
        f"Summa: {format_money(amount)}\n"
        f"Usul: {method_name}\n\n"
        "Admin tasdiqlashini kuting. Holatni «📦 Buyurtmalarim» bo'limida ham kuzatasiz.",
        reply_markup=main_menu_keyboard(),
    )

    admin_text = (
        "💳 YANGI TO'LOV CHEKI\n"
        f"ID: #{payment_id}\n"
        f"Foydalanuvchi: {message.from_user.id}\n"
        f"Summa: {format_money(amount)}\n"
        f"Usul: {method_name}"
    )
    from keyboards.inline import admin_payment_kb

    await notify_admins(bot, admin_text, admin_payment_kb(int(payment_id)))
    log.info("Chek qabul qilindi: #%s (user=%s)", payment_id, message.from_user.id)


@router.message(TopUpSG.receipt)
async def receipt_other(message: Message) -> None:
    await message.answer(
        "⚠️ Chek sifatida rasm, PDF hujjat yoki matn yuboring.",
        reply_markup=back_reply_kb(),
    )


# ------------------------------------------------- Telegram Stars invoice
@router.callback_query(F.data.startswith("topstars:"))
async def send_stars_invoice(callback: CallbackQuery, bot: Bot) -> None:
    raw = callback.data.split(":")[-1]
    if not raw.isdigit():
        await send(callback, t("invalid_input"))
        return
    stars = int(raw)
    if stars <= 0 or stars > 100_000:
        await send(callback, t("invalid_input"))
        return

    rate = await payment_service.stars_rate()
    description = (
        f"{stars} ⭐ hisobingizga qo'shiladi."
        + (f" (≈ {format_money(stars * rate)})" if rate > 0 else "")
    )
    try:
        await bot.send_invoice(
            chat_id=callback.message.chat.id if callback.message else callback.from_user.id,
            title="Telegram Stars to'ldirish",
            description=description,
            payload=payment_service.stars_payload(callback.from_user.id, stars),
            currency="XTR",
            prices=payment_service.stars_prices(stars),
            provider_token=None,
        )
        await callback.answer()
    except Exception as exc:  # noqa: BLE001
        log.warning("Invoice yuborilmadi: %s", type(exc).__name__)
        await callback.answer("Invoice yuborilmadi. Keyinroq urinib ko'ring.", show_alert=True)


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    parsed = payment_service.parse_stars_payload(query.invoice_payload)
    if parsed is None:
        await query.answer(ok=False, error_message="Noto'g'ri so'rov. Qaytadan urinib ko'ring.")
        return
    user_id, stars = parsed
    if int(user_id) != int(query.from_user.id):
        await query.answer(ok=False, error_message="Bu to'lov boshqa foydalanuvchiga tegishli.")
        return
    if stars <= 0:
        await query.answer(ok=False, error_message="Miqdor noto'g'ri.")
        return
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot) -> None:
    payment = message.successful_payment
    parsed = payment_service.parse_stars_payload(payment.invoice_payload)
    if parsed is None:
        log.warning("Noto'g'ri invoice payload: user=%s", message.from_user.id)
        return
    _, stars = parsed

    ok, credited = await payment_service.credit_stars(
        message.from_user.id,
        stars,
        payment.telegram_payment_charge_id,
    )
    if not ok:
        await message.answer(
            "⚠️ To'lov qayta ishlanmadi yoki kurs sozlanmagan.\nAdmin bilan bog'laning.",
            reply_markup=main_menu_keyboard(),
        )
        return

    user = await db.get_user(message.from_user.id) or {}
    await message.answer(
        "✅ TO'LDIRISH MUVAFFAQIYATLI!\n\n"
        f"Yo'ldozlar: {stars} ⭐\n"
        f"Qo'shildi: {format_money(credited)}\n"
        f"Yangi balans: {format_money(int(user.get('balance') or 0))}",
        reply_markup=main_menu_keyboard(),
    )
    await notify_admins(
        bot,
        "⭐ TELEGRAM STARS TO'LDIRISH\n"
        f"Foydalanuvchi: {message.from_user.id}\n"
        f"Miqdor: {stars} ⭐\n"
        f"Hisobga: {format_money(credited)}",
    )


__all__ = ["router", "TopUpSG"]
