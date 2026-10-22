"""Start, asosiy menyu matnlari va umumiy tugmalar (Qo'llanma, Yordam, Hamkorlik)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import db
from keyboards.inline import back_kb
from keyboards.main_menu import main_menu_keyboard
from services import referral_service
from utils.helpers import is_admin, send
from utils.i18n import t
from utils.logger import get_logger
from utils.validators import format_money

log = get_logger("start")
router = Router()


def _profile_lines(user: dict, ref_ok: bool = False, is_new: bool = False) -> list[str]:
    lines: list[str] = []
    if is_new:
        lines += ["🎉 Siz ro'yxatdan o'tdingiz!", ""]
    if ref_ok:
        lines += ["🤝 Siz taklif havolasi orqali keldingiz. Do'stingizga bonus beriladi!", ""]
    lines.append(f"💰 Balansingiz: {format_money(int(user.get('balance') or 0))}")
    return lines


async def _service_notice() -> str:
    notice = (await db.get_setting("service_notice", "")) or ""
    return notice.strip()


# ------------------------------------------------------------------------ /start
@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject, state: FSMContext) -> None:
    await state.clear()

    user, is_new = await db.get_or_create_user(
        message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name or "",
    )

    if int(user.get("is_banned") or 0):
        await message.answer("⛔ Hisobingiz cheklangan.\nSavol uchun admin bilan bog'laning.")
        return

    ref_ok = False
    if command.args:
        ref_ok, _ = await referral_service.process_referral(user, command.args)

    text = t("welcome", balance=format_money(int(user.get("balance") or 0)))
    lines = _profile_lines(user, ref_ok=ref_ok, is_new=is_new)
    text += "\n" + "\n".join(lines)

    notice = await _service_notice()
    if notice:
        text += f"\n\n📣 E'lon:\n{notice}"

    if is_admin(message.from_user.id):
        text += "\n\n🔑 Admin panel: /admin"

    await message.answer(text, reply_markup=main_menu_keyboard())
    log.info("/start: user=%s (%s)", message.from_user.id, "yangi" if is_new else "mavjud")


# --------------------------------------------------------------------- callback
@router.callback_query(F.data == "menu")
async def cb_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(callback.from_user.id) or {}
    text = t("welcome", balance=format_money(int(user.get("balance") or 0)))
    notice = await _service_notice()
    if notice:
        text += f"\n\n📣 E'lon:\n{notice}"
    await callback.answer()
    if callback.message:
        await callback.message.answer(text, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ----------------------------------------------------------------- Qo'llanma
async def guide_text() -> str:
    return t("guide")


@router.message(F.text == t("btn_guide"))
@router.message(Command("guide"))
async def cmd_guide(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(await guide_text(), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "guide")
async def cb_guide(callback: CallbackQuery) -> None:
    await send(callback, await guide_text(), back_kb())


# --------------------------------------------------------------------- Yordam
async def help_text() -> str:
    text = t("help")
    notice = await _service_notice()
    if notice:
        text += f"\n\n📣 E'lon:\n{notice}"
    return text


@router.message(F.text == t("btn_help"))
@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(await help_text(), reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    await send(callback, await help_text(), back_kb())


# ------------------------------------------------------------------ Hamkorlik
async def partner_text(user_id: int) -> str:
    stats = await referral_service.user_stats(user_id)
    link = referral_service.referral_link(user_id)
    return (
        "🤝 HAMKORLIK DASTURI\n\n"
        "Do'stlaringizni taklif qiling va har bir buyurtmadan bonus oling!\n\n"
        f"🎯 Bonus (1 do'st uchun): {format_money(stats['bonus'])}\n"
        f"👥 Taklif qilinganlar: {stats['invited']}\n"
        f"✅ Faol (birinchi buyurtma bergan): {stats['active']}\n"
        f"💰 Shu orqali: {format_money(stats['earned'])}\n\n"
        "Shaxsiy havolangiz:\n"
        f"{link}\n\n"
        "Qoidalar:\n"
        "• O'zini o'zi taklif qilib bo'lmaydi.\n"
        "• Bonus taklif qilingan odam birinchi buyurtma berganda beriladi.\n"
        "• Soxta takliflar (bot, takroriy hisoblar) aniqlansa — bekor qilinadi."
    )


@router.message(F.text == t("btn_partner"))
@router.message(Command("partner"))
async def cmd_partner(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(await partner_text(message.from_user.id), reply_markup=main_menu_keyboard())
    # Referal bo'limiga o'tish uchun alohida tugma yuboramiz
    await message.answer("Havolangizni ko'rish uchun 👇", reply_markup=back_kb("ref"))


@router.callback_query(F.data == "partner")
async def cb_partner(callback: CallbackQuery) -> None:
    await send(callback, await partner_text(callback.from_user.id), back_kb("ref"))


# ------------------------------------------------------------- Asosiy menyuga
async def show_main_menu(message: Message, state: FSMContext | None = None) -> None:
    """Holatni tozalab, asosiy menyuni ko'rsatadi (FSM handlerlardan chaqiriladi)."""
    if state is not None:
        await state.clear()
    user = await db.get_user(message.from_user.id) or {}
    text = t("welcome", balance=format_money(int(user.get("balance") or 0)))
    notice = await _service_notice()
    if notice:
        text += f"\n\n📣 E'lon:\n{notice}"
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(F.text.in_({t("btn_back"), t("btn_menu")}))
@router.message(Command("menu"))
async def cmd_back_to_menu(message: Message, state: FSMContext) -> None:
    await show_main_menu(message, state)


# ------------------------------------------------------- boshqa foydalanuvchi
@router.message(Command("admin"))
async def cmd_admin_denied(message: Message) -> None:
    await message.answer(t("admin_denied"))


# --------------------------------------------- eskirgan / nomalum tugmalar
@router.callback_query()
async def cb_stale(callback: CallbackQuery) -> None:
    await callback.answer(t("stale_button"), show_alert=False)
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass


__all__ = ["router"]
