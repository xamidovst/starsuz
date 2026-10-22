"""Barcha InlineKeyboard yasovchilar (foydalanuvchi + admin).

Callback data formatlari (handlers/* fayllar shularni tinglaydi):
    menu, back, stars, premium, gifts, <ptype>:buy:<id>, <ptype>:order:<id>,
    myorders, order:<no>, pay:<no>, cancel:<no>, topup, topup:<mid>,
    topstars:<n>, promo, ref, guide, help, partner
    adm:... (admin panel)
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import ORDER_STATUSES, PAYMENT_STATUSES
from utils.i18n import t
from utils.validators import format_money

PTYPE_LABELS = {"stars": "⭐ Stars", "premium": "💎 Premium", "gift": "🎁 Sovg'alar"}


# --------------------------------------------------------------------------- umumiy
def _kb(builder: InlineKeyboardBuilder) -> InlineKeyboardMarkup:
    return builder.as_markup()


def back_kb(data: str = "menu") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=t("btn_back"), callback_data=data)
    return _kb(b)


def menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Asosiy menyu", callback_data="menu")
    return _kb(b)


def yes_no_kb(yes_data: str, no_data: str, yes_text: str = "✅ Tasdiqlash",
              no_text: str = "❌ Rad etish") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=yes_text, callback_data=yes_data)
    b.button(text=no_text, callback_data=no_data)
    b.adjust(2)
    return _kb(b)


# --------------------------------------------------------------- foydalanuvchi
def _price_label(product: dict) -> str:
    price = int(product.get("price") or 0)
    if price > 0:
        return format_money(price)
    return "⏳ narx belgilanmagan"


def products_kb(ptype: str, products: list[dict], back_data: str = "menu") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for product in products:
        meta = _meta(product)
        if meta.get("custom"):
            label = f"✍️ {product['name']}"
        else:
            label = f"{product['name']} — {_price_label(product)}"
        b.button(text=label, callback_data=f"{ptype}:buy:{product['id']}")
    b.button(text=t("btn_back"), callback_data=back_data)
    b.adjust(1)
    return _kb(b)


def product_detail_kb(ptype: str, product: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    meta = _meta(product)
    price = int(product.get("price") or 0)
    if meta.get("custom"):
        b.button(text="✍️ Miqdorni kiritish", callback_data=f"{ptype}:custom")
    elif price > 0:
        b.button(text="📦 Buyurtma berish", callback_data=f"{ptype}:order:{product['id']}")
    else:
        b.button(text="⏳ Narx hali belgilanmagan", callback_data="noop")
    b.button(text="🔙 Orqaga", callback_data=f"{ptype}")
    b.adjust(1)
    return _kb(b)


def order_actions_kb(order_no: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💰 Balans bilan to'lash", callback_data=f"pay:{order_no}")
    b.button(text="📦 Buyurtmalarim", callback_data="myorders")
    b.button(text="❌ Buyurtmani bekor qilish", callback_data=f"cancel:{order_no}")
    b.button(text="🏠 Asosiy menyu", callback_data="menu")
    b.adjust(1)
    return _kb(b)


def orders_list_kb(orders: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for order in orders:
        status = ORDER_STATUSES.get(order["status"], order["status"])
        b.button(text=f"{order['order_no']} — {status}", callback_data=f"order:{order['order_no']}")
    b.button(text="🏠 Asosiy menyu", callback_data="menu")
    b.adjust(1)
    return _kb(b)


def topup_methods_kb(methods: list[dict], stars_enabled: bool = True) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for method in methods:
        if not method.get("active", True):
            continue
        b.button(text=f"💳 {method['name']}", callback_data=f"topup:{method['id']}")
    if stars_enabled:
        b.button(text="⭐ Telegram Stars orqali", callback_data="topup:stars")
    b.button(text="🏠 Asosiy menyu", callback_data="menu")
    b.adjust(1)
    return _kb(b)


def topup_stars_kb(presets: list[int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for amount in presets:
        b.button(text=f"{amount} ⭐", callback_data=f"topstars:{amount}")
    b.button(text="🔙 Orqaga", callback_data="topup")
    b.adjust(2)
    return _kb(b)


def topup_amount_kb(minimum: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for step in (10_000, 50_000, 100_000, 500_000):
        if step >= minimum:
            b.button(text=format_money(step), callback_data=f"topamount:{step}")
    b.button(text="✏️ Boshqa summa", callback_data="topamount:custom")
    b.button(text="🔙 Orqaga", callback_data="topup")
    b.adjust(2)
    return _kb(b)


# ------------------------------------------------------------------- admin panel
def admin_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        ("📊 Statistika", "adm:stats"),
        ("👥 Foydalanuvchilar", "adm:users"),
        ("📦 Buyurtmalar", "adm:orders"),
        ("💳 To'lovlar", "adm:payments"),
        ("💰 Balans boshqaruvi", "adm:bal"),
        ("🔍 Foydalanuvchi qidirish", "adm:search"),
        ("⭐ Stars mahsulotlari", "adm:pr:stars"),
        ("💎 Premium tariflari", "adm:pr:premium"),
        ("🎁 Sovg'alar katalogi", "adm:pr:gift"),
        ("🎟 Promo-kodlar", "adm:promo"),
        ("👥 Referallar statistikasi", "adm:refs"),
        ("📢 Ommaviy xabar", "adm:bcast"),
        ("💳 To'lov usullari", "adm:paym"),
        ("⚙️ Bot sozlamalari", "adm:set"),
        ("🧾 Admin jurnali", "adm:logs"),
    ]
    b = InlineKeyboardBuilder()
    for text, data in rows:
        b.button(text=text, callback_data=data)
    b.adjust(2)
    return _kb(b)


def admin_back_kb(target: str = "adm:menu") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 Orqaga", callback_data=target)
    return _kb(b)


def admin_users_kb(users: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for user in users:
        name = user.get("username") or user.get("full_name") or "—"
        if isinstance(name, str) and name.startswith("@"):
            pass
        label = f"{name} | {user['telegram_id']}"
        b.button(text=label[:64], callback_data=f"adm:u:{user['telegram_id']}")
    b.button(text="🔙 Orqaga", callback_data="adm:menu")
    b.adjust(1)
    return _kb(b)


def admin_user_kb(user_id: int, banned: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💰 Balans qo'shish", callback_data=f"adm:baladd:{user_id}")
    b.button(text="➖ Balans ayirish", callback_data=f"adm:balcut:{user_id}")
    b.button(text=("🚫 Blokdan chiqarish" if banned else "🚫 Bloklash"), callback_data=f"adm:ban:{user_id}")
    b.button(text="📦 Buyurtmalari", callback_data=f"adm:uorders:{user_id}")
    b.button(text="🔙 Orqaga", callback_data="adm:users")
    b.adjust(1)
    return _kb(b)


def admin_orders_kb(orders: list[dict], status: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for order in orders:
        status_label = ORDER_STATUSES.get(order["status"], order["status"])
        b.button(text=f"{order['order_no']} — {status_label}", callback_data=f"adm:o:{order['id']}")
    for key, label in (
        ("awaiting_payment", "💳 To'lov kutilmoqda"),
        ("pending", "🕓 Kutilmoqda"),
        ("processing", "⚙️ Bajarilmoqda"),
        ("completed", "✅ Bajarildi"),
        ("cancelled", "❌ Bekor qilindi"),
    ):
        if key != status:
            b.button(text=label, callback_data=f"adm:ol:{key}")
    b.button(text="🔙 Orqaga", callback_data="adm:menu")
    b.adjust(1)
    return _kb(b)


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⚙️ Bajarilmoqda", callback_data=f"adm:o:{order_id}:processing")
    b.button(text="✅ Bajarildi", callback_data=f"adm:o:{order_id}:completed")
    b.button(text="❌ Rad etish (pul qaytariladi)", callback_data=f"adm:o:{order_id}:cancelled")
    b.button(text="🔙 Orqaga", callback_data="adm:orders")
    b.adjust(1)
    return _kb(b)


def admin_payments_kb(payments: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for payment in payments:
        label = f"#{payment['id']} | {format_money(payment['amount'])} | {payment['method']}"
        b.button(text=label[:64], callback_data=f"adm:p:{payment['id']}")
    b.button(text="🔙 Orqaga", callback_data="adm:menu")
    b.adjust(1)
    return _kb(b)


def admin_payment_kb(payment_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"adm:p:{payment_id}:ok")
    b.button(text="❌ Rad etish", callback_data=f"adm:p:{payment_id}:no")
    b.button(text="🔙 Orqaga", callback_data="adm:payments")
    b.adjust(2, 1)
    return _kb(b)


def admin_products_kb(ptype: str, products: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for product in products:
        mark = "✅" if product["is_active"] else "❌"
        b.button(text=f"{mark} {product['name']} — {_price_label(product)}"[:64],
                 callback_data=f"adm:pr:{ptype}:p{product['id']}")
    b.button(text="➕ Yangi mahsulot", callback_data=f"adm:new:{ptype}")
    b.button(text="🔙 Orqaga", callback_data="adm:menu")
    b.adjust(1)
    return _kb(b)


def admin_product_kb(ptype: str, product_id: int, active: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💲 Narxni o'zgartirish", callback_data=f"adm:pr:{ptype}:p{product_id}:price")
    b.button(text=("❌ Vaqtincha o'chirish" if active else "✅ Faollashtirish"),
             callback_data=f"adm:pr:{ptype}:p{product_id}:toggle")
    b.button(text="🔙 Orqaga", callback_data=f"adm:pr:{ptype}")
    b.adjust(1)
    return _kb(b)


def admin_promo_kb(promos: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for promo in promos:
        mark = "✅" if promo["is_active"] else "❌"
        b.button(text=f"{mark} {promo['code']} (+{format_money(promo['bonus'])})"[:64],
                 callback_data=f"adm:pc:{promo['id']}")
    b.button(text="➕ Yangi promo-kod", callback_data="adm:pc:new")
    b.button(text="🔙 Orqaga", callback_data="adm:menu")
    b.adjust(1)
    return _kb(b)


def admin_promo_item_kb(promo_id: int, active: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=("❌ Kodni o'chirish" if active else "✅ Kodni yoqish"),
             callback_data=f"adm:pc:{promo_id}:toggle")
    b.button(text="🗑 Butunlay o'chirish", callback_data=f"adm:pc:{promo_id}:del")
    b.button(text="🔙 Orqaga", callback_data="adm:promo")
    b.adjust(1)
    return _kb(b)


def admin_methods_kb(methods: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for method in methods:
        mark = "✅" if method.get("active", True) else "❌"
        b.button(text=f"{mark} {method['name']}"[:64], callback_data=f"adm:paym:{method['id']}")
    b.button(text="➕ Yangi usul", callback_data="adm:paym:new")
    b.button(text="🔙 Orqaga", callback_data="adm:menu")
    b.adjust(1)
    return _kb(b)


def admin_method_item_kb(method_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Rekvizitni tahrirlash", callback_data=f"adm:paym:{method_id}:edit")
    b.button(text="🔁 Yoqish/O'chirish", callback_data=f"adm:paym:{method_id}:toggle")
    b.button(text="🗑 O'chirish", callback_data=f"adm:paym:{method_id}:del")
    b.button(text="🔙 Orqaga", callback_data="adm:paym")
    b.adjust(1)
    return _kb(b)


SETTING_ROWS: tuple[tuple[str, str, str], ...] = (
    ("referral_bonus", "👥 Referal bonusi (so'm)", "ADM_SET referral_bonus"),
    ("stars_unit_price", "⭐ 1 Stars narxi — maxsus buyurtma (so'm)", "ADM_SET stars_unit_price"),
    ("stars_topup_rate", "⭐ Stars orqali to'ldirish kursi (so'm)", "ADM_SET stars_topup_rate"),
    ("min_topup", "💳 Minimal to'ldirish (so'm)", "ADM_SET min_topup"),
    ("max_topup", "💳 Maksimal to'ldirish (so'm)", "ADM_SET max_topup"),
    ("custom_stars_min", "✍️ Maxsus Stars — min", "ADM_SET custom_stars_min"),
    ("custom_stars_max", "✍️ Maxsus Stars — max", "ADM_SET custom_stars_max"),
    ("broadcast_delay_ms", "📢 Xabarlar orasidagi kechikish (ms)", "ADM_SET broadcast_delay_ms"),
    ("service_notice", "📝 Umumiy e'lon (menyuda chiqadi)", "ADM_SET service_notice"),
)


def admin_settings_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label, _ in SETTING_ROWS:
        b.button(text=label, callback_data=f"adm:edit:{key}")
    b.button(text="🔙 Orqaga", callback_data="adm:menu")
    b.adjust(1)
    return _kb(b)


def admin_stats_kb() -> InlineKeyboardMarkup:
    return admin_back_kb("adm:menu")


__all__ = [
    "back_kb", "menu_kb", "yes_no_kb", "products_kb", "product_detail_kb",
    "order_actions_kb", "orders_list_kb", "topup_methods_kb", "topup_stars_kb",
    "topup_amount_kb", "admin_menu_kb", "admin_back_kb", "admin_users_kb",
    "admin_user_kb", "admin_orders_kb", "admin_order_kb", "admin_payments_kb",
    "admin_payment_kb", "admin_products_kb", "admin_product_kb", "admin_promo_kb",
    "admin_promo_item_kb", "admin_methods_kb", "admin_method_item_kb",
    "admin_settings_kb", "admin_stats_kb", "SETTING_ROWS", "PTYPE_LABELS",
]


def _meta(product: dict) -> dict:
    import json

    raw = product.get("meta") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


# PAYMENT_STATUSES export (admin matnlarida ishlatiladi)
__all__.append("PAYMENT_STATUSES")
