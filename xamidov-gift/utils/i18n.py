"""Tillar uchun matnlar (i18n).

Hozircha faqat o'zbekcha to'liq. Rus va inglizcha qo'shish uchun
`TEXTS` lug'atiga "ru" va "en" kalitlarini qo'shish kifoya —
butun kod o'zgarmaydi, `t()` funksiyasi avtomatik tarjima qiladi.

Til tanlash: users jadvalidagi `lang` ustuni (hozircha hamma uchun "uz").
"""

from __future__ import annotations

DEFAULT_LANG = "uz"
SUPPORTED_LANGS = ("uz", "ru", "en")

_UZ: dict[str, str] = {
    # --- Salomlashuv ---
    "welcome": (
        "Assalomu alaykum! 👋\n"
        "XAMIDOV GIFT botiga xush kelibsiz! 🎁\n\n"
        "Bu yerda Telegram Stars, Telegram Premium va sovg'alar "
        "bo'yicha buyurtma berishingiz mumkin.\n\n"
        "Balansingiz: {balance}\n"
        "Tanlang 👇"
    ),
    # --- Asosiy menyu tugmalari ---
    "btn_stars": "⭐ Stars sotib olish",
    "btn_premium": "💎 Premium sotib olish",
    "btn_gifts": "🎁 Telegram sovg'alar",
    "btn_kabinet": "👤 Kabinet",
    "btn_topup": "💳 Hisobni to'ldirish",
    "btn_promo": "🎟 Promo-kod",
    "btn_referral": "👥 Referal tizimi",
    "btn_orders": "📦 Buyurtmalarim",
    "btn_guide": "📖 Qo'llanma",
    "btn_partner": "🤝 Hamkorlik",
    "btn_help": "💬 Yordam",
    "btn_back": "🔙 Orqaga",
    "btn_menu": "🏠 Asosiy menyu",
    # --- Umumiy ---
    "choose": "Tanlang 👇",
    "back": "🔙 Orqaga",
    "cancel": "❌ Bekor qilish",
    "error": "Kutilmagan xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring.",
    "guide": (
        "📖 QO'LLANMA\n\n"
        "1️⃣ Hisobingizni to'ldiring (💳 Hisobni to'ldirish).\n"
        "2️⃣ Kerakli bo'limni tanlang: Stars, Premium yoki sovg'a.\n"
        "3️⃣ Buyurtma bering va to'lovni tasdiqlang.\n"
        "4️⃣ Buyurtma holatini \"📦 Buyurtmalarim\" bo'limida kuzating.\n\n"
        "Savol bo'lsa — 💬 Yordam tugmasi orqali yozing."
    ),
    "help": (
        "💬 YORDAM\n\n"
        "Muammo yuzaga kelsa, quyidagilarni biling:\n"
        "• Buyurtma holatini \"📦 Buyurtmalarim\" dan ko'rasiz.\n"
        "• To'lov cheki tasdiqlanmasa — admin bilan bog'laning.\n"
        "• Admin bilan bog'lanish: yuqoridagi havola orqali yozing.\n\n"
        "Biz doim yordam berishga tayyormiz! 🤝"
    ),
    "empty": "Hozircha ma'lumot yo'q.",
    "invalid_input": "⚠️ Noto'g'ri qiymat kiritildi. Qaytadan urinib ko'ring.",
    "admin_denied": "⛔ Bu buyruq faqat admin uchun.",
    "stale_button": "⚠️ Tugma eskirgan. Asosiy menyudan qaytadan tanlang.",
}

# Kalit bo'sh bo'lsa — DEFAULT_LANG dagi matn qaytariladi.
TEXTS: dict[str, dict[str, str]] = {"uz": _UZ}

# Xabarnomalarda ishlatiladigan menyu tugmalari matnlari
_MENU_KEYS = (
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
    "btn_back",
    "btn_menu",
)


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Matnni oladi. Topilmasa — o'zbekcha, u ham bo'lmasa — kalit nomi."""
    table = TEXTS.get(lang) or TEXTS[DEFAULT_LANG]
    text = table.get(key)
    if text is None:
        text = TEXTS[DEFAULT_LANG].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


def menu_texts(lang: str = DEFAULT_LANG) -> frozenset[str]:
    """Asosiy menyu tugmalarining matnlari to'plami (FSM handlerlarida tekshirish uchun)."""
    return frozenset(t(k, lang) for k in _MENU_KEYS)


__all__ = ["t", "menu_texts", "TEXTS", "DEFAULT_LANG", "SUPPORTED_LANGS"]
