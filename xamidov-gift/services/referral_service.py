"""Referal tizimi: taklif havolasi, bonus berish, statistika."""

from __future__ import annotations

from config import BOT_USERNAME
from database import db
from utils.logger import get_logger

log = get_logger("referral")


def referral_link(user_id: int) -> str:
    """Foydalanuvchining shaxsiy taklif havolasi."""
    if not BOT_USERNAME:
        return "Havola yaratish uchun BOT_USERNAME sozlanmagan (.env)."
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"


def parse_ref_arg(args: str | None) -> int | None:
    """"ref_123456" ko'rinishidagi argumentdan taklif qiluvchi ID sini oladi."""
    if not args:
        return None
    text = args.strip()
    if not text.lower().startswith("ref_"):
        return None
    raw = text[4:].strip()
    if not raw.isdigit():
        return None
    return int(raw)


async def process_referral(user: dict, args: str | None) -> tuple[bool, str]:
    """/start argumentidan referalni qaydga olish.

    Returns: (qayd qilindi_mi, xabar)
    """
    referrer_id = parse_ref_arg(args)
    if referrer_id is None:
        return False, ""

    referred_id = int(user["telegram_id"])
    if referrer_id == referred_id:
        log.info("O'zini o'zi taklif qilish bloklandi: %s", referred_id)
        return False, ""

    if user.get("referred_by"):
        return False, ""

    ok, reason = await db.add_referral(referrer_id, referred_id)
    if ok:
        await db.execute(
            "UPDATE users SET referred_by = ? WHERE telegram_id = ?", (referrer_id, referred_id)
        )
        log.info("Referal qayd qilindi: %s → %s", referrer_id, referred_id)
        return True, "ok"

    log.info("Referal rad etildi (%s): %s", referred_id, reason)
    return False, reason


async def on_first_purchase(user_id: int, bot=None) -> bool:
    """Taklif qilingan odam birinchi haqiqiy xarid qilganda — bonus beriladi.

    Idempotent: ikkinchi marta chaqirilsa — hech narsa qilmaydi.
    """
    granted, referrer_id = await db.activate_referral(int(user_id))
    if not granted or referrer_id is None:
        return False

    log.info("Referal bonusi berildi: user=%s", referrer_id)
    if bot is not None:
        from utils.helpers import safe_send

        settings = await db.get_settings()
        bonus = settings.get("referral_bonus", "0")
        await safe_send(
            bot,
            int(referrer_id),
            "🎉 Tabriklaymiz!\n\n"
            f"Siz taklif qilingan do'stingiz birinchi buyurtmani berdi.\n"
            f"Hisobingizga {bonus} so'm bonus qo'shildi! 💰",
        )
    return True


async def user_stats(user_id: int) -> dict:
    """Kabinet/Referal bo'limi uchun shaxsiy statistika."""
    user = await db.get_user(user_id) or {}
    invited = await db.fetchone(
        "SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (user_id,)
    )
    active = await db.fetchone(
        "SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ? AND status = 'active'", (user_id,)
    )
    return {
        "invited": int(invited["c"]) if invited else 0,
        "active": int(active["c"]) if active else 0,
        "earned": int(user.get("referral_bonus_total") or 0),
        "bonus": int((await db.get_settings()).get("referral_bonus", "0") or 0),
    }


async def is_enabled() -> bool:
    return (await db.get_setting("referral_enabled", "1")) == "1"


__all__ = [
    "referral_link",
    "parse_ref_arg",
    "process_referral",
    "on_first_purchase",
    "user_stats",
    "is_enabled",
]
