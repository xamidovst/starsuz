"""XAMIDOV GIFT — SQLite ma'lumotlar bazasi.

Tanlovlar:
* async (aiosqlite) — bot async ishlagani uchun;
* bitta ulanish + asyncio.Lock — ayni vaqtda bitta yozuv, shuning uchun
  ko'p qadamli amallar (masalan balans o'zgartirish) atomar bo'ladi;
* BEGIN IMMEDIATE / COMMIT / ROLLBACK — xatolikda ham ma'lumot yarim
  holatda qolmaydi, bir to'lov ikki marta hisoblanmaydi.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import aiosqlite

from config import DB_PATH
from utils.logger import get_logger

log = get_logger("db")

# ---------------------------------------------------------------------------
# Holatlar (status) — barcha modullar shu yerdan oladi
# ---------------------------------------------------------------------------

ORDER_STATUSES: dict[str, str] = {
    "awaiting_payment": "💳 To'lov kutilmoqda",
    "pending": "🕓 Kutilmoqda",
    "processing": "⚙️ Bajarilmoqda",
    "completed": "✅ Bajarildi",
    "cancelled": "❌ Bekor qilindi",
}

PAYMENT_STATUSES: dict[str, str] = {
    "pending": "🕓 Tekshiruvda",
    "approved": "✅ Tasdiqlandi",
    "rejected": "❌ Rad etildi",
}

# Mahsulot turlari
PTYPE_STARS = "stars"
PTYPE_PREMIUM = "premium"
PTYPE_GIFT = "gift"
PTYPES = (PTYPE_STARS, PTYPE_PREMIUM, PTYPE_GIFT)


def now_iso() -> str:
    """UTC vaqt, ISO ko'rinishida (jadval ustunlari uchun)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _dicts(cursor: aiosqlite.Cursor, rows: list[Any]) -> list[dict[str, Any]]:
    if not cursor.description:
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in rows]


# Standart sozlamalar (faqat birinchi ishga tushirishda yoziladi)
DEFAULT_SETTINGS: dict[str, str] = {
    "referral_bonus": "5000",            # faol taklif uchun beriladigan bonus (so'm)
    "referral_enabled": "1",
    "stars_unit_price": "600",           # maxsus Stars uchun 1 star narxi (so'm)
    "stars_topup_rate": "600",           # Stars orqali to'langanda 1 star = ? so'm
    "stars_topup_presets": "15,50,100,250",  # Stars orqali to'ldirish paketlari
    "min_topup": "5000",                 # minimal to'ldirish (so'm)
    "max_topup": "100000000",            # maksimal to'ldirish (so'm)
    "custom_stars_min": "10",
    "custom_stars_max": "100000",
    "payment_methods": "[]",             # JSON: [{id, name, details, active}]
    "broadcast_delay_ms": "50",
    "service_notice": "",                # menyuda ko'rsatiladigan qo'shimcha e'lon
}

# Dastlabki mahsulotlar — narxi 0 («hali belgilanmagan»).
# Narxlar faqat admin panelidan o'zgartiriladi, kodga yozilmaydi.
SEED_PRODUCTS: list[dict[str, Any]] = [
    {"ptype": "stars", "name": "50 Stars", "meta": {"stars": 50}, "sort": 1},
    {"ptype": "stars", "name": "100 Stars", "meta": {"stars": 100}, "sort": 2},
    {"ptype": "stars", "name": "250 Stars", "meta": {"stars": 250}, "sort": 3},
    {"ptype": "stars", "name": "500 Stars", "meta": {"stars": 500}, "sort": 4},
    {"ptype": "stars", "name": "1000 Stars", "meta": {"stars": 1000}, "sort": 5},
    {"ptype": "stars", "name": "Boshqa miqdor", "meta": {"custom": True}, "sort": 6},
    {"ptype": "premium", "name": "1 oylik Premium", "meta": {"days": 30}, "sort": 1},
    {"ptype": "premium", "name": "3 oylik Premium", "meta": {"days": 90}, "sort": 2},
    {"ptype": "premium", "name": "6 oylik Premium", "meta": {"days": 180}, "sort": 3},
    {"ptype": "premium", "name": "12 oylik Premium", "meta": {"days": 365}, "sort": 4},
    {"ptype": "gift", "name": "Rose", "meta": {"emoji": "🌹"}, "sort": 1},
    {"ptype": "gift", "name": "Cake", "meta": {"emoji": "🎂"}, "sort": 2},
    {"ptype": "gift", "name": "Balloon", "meta": {"emoji": "🎈"}, "sort": 3},
    {"ptype": "gift", "name": "Cookie", "meta": {"emoji": "🍪"}, "sort": 4},
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id           INTEGER NOT NULL UNIQUE,
    username              TEXT,
    full_name             TEXT NOT NULL DEFAULT '',
    balance               INTEGER NOT NULL DEFAULT 0,
    lang                  TEXT NOT NULL DEFAULT 'uz',
    referred_by           INTEGER,
    referrals_count       INTEGER NOT NULL DEFAULT 0,
    referral_bonus_total  INTEGER NOT NULL DEFAULT 0,
    promo_bonus_total     INTEGER NOT NULL DEFAULT 0,
    orders_count          INTEGER NOT NULL DEFAULT 0,
    is_banned             INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ptype         TEXT NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    price         INTEGER NOT NULL DEFAULT 0,
    meta          TEXT NOT NULL DEFAULT '{}',
    image_file_id TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    sort_order    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_products_ptype ON products(ptype, is_active);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no     TEXT NOT NULL UNIQUE,
    user_id      INTEGER NOT NULL,
    product_id   INTEGER,
    ptype        TEXT NOT NULL,
    product_name TEXT NOT NULL,
    amount       INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'awaiting_payment',
    paid_via     TEXT,
    details      TEXT NOT NULL DEFAULT '{}',
    admin_note   TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

CREATE TABLE IF NOT EXISTS payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    method        TEXT NOT NULL,
    amount        INTEGER NOT NULL DEFAULT 0,
    receipt_key   TEXT UNIQUE,       -- chek identifikatori (qayta ishlatish taqiqlanadi)
    receipt_ref   TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',
    tg_charge_id  TEXT UNIQUE,       -- Telegram Stars to'lovi (bir marta)
    admin_id      INTEGER,
    note          TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    processed_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    ttype         TEXT NOT NULL,     -- topup|purchase|refund|bonus|promo|adjust
    amount        INTEGER NOT NULL,  -- musbat/qiymat balansga qo'shiladi
    balance_after INTEGER NOT NULL,
    ref_id        INTEGER,
    note          TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id, created_at);

CREATE TABLE IF NOT EXISTS promo_codes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT NOT NULL UNIQUE,
    bonus         INTEGER NOT NULL DEFAULT 0,
    description   TEXT NOT NULL DEFAULT '',
    expires_at    TEXT,              -- NULL = cheksiz
    max_uses      INTEGER NOT NULL DEFAULT 0,   -- 0 = cheksiz
    used_count    INTEGER NOT NULL DEFAULT 0,
    per_user_limit INTEGER NOT NULL DEFAULT 1,  -- bir foydalanuvchiga
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_usages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    amount    INTEGER NOT NULL DEFAULT 0,
    used_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_promo_usage ON promo_usages(code_id, user_id);

CREATE TABLE IF NOT EXISTS referrals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id  INTEGER NOT NULL,
    referred_id  INTEGER NOT NULL UNIQUE,
    bonus        INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending|active
    created_at   TEXT NOT NULL,
    activated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_ref_referrer ON referrals(referrer_id);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id   INTEGER NOT NULL,
    action     TEXT NOT NULL,
    details    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""


class Database:
    """Bitta ulanish orqali barcha DB amallari (async, xavfsiz)."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        self.path = Path(path)
        self.conn: aiosqlite.Connection | None = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ utils
    def _require(self) -> aiosqlite.Connection:
        if self.conn is None:
            raise RuntimeError("Baza ulanmagan. Avval await db.connect() chaqiring.")
        return self.conn

    @asynccontextmanager
    async def _tx(self) -> Iterator[aiosqlite.Connection]:
        """Atomar tranzaksiya: boshida BEGIN, xatoda ROLLBACK."""
        conn = self._require()
        async with self._lock:
            await conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                await conn.execute("COMMIT")
            except BaseException:
                await conn.execute("ROLLBACK")
                raise

    # Barcha alohida metodlar shu lock ostida ishlaydi (yozuvlar aralmaydi)
    async def fetchall(self, sql: str, params: tuple | list = ()) -> list[dict]:
        conn = self._require()
        async with self._lock:
            cur = await conn.execute(sql, params)
            rows = await cur.fetchall()
            return _dicts(cur, rows)

    async def fetchone(self, sql: str, params: tuple | list = ()) -> dict | None:
        conn = self._require()
        async with self._lock:
            cur = await conn.execute(sql, params)
            row = await cur.fetchone()
            if row is None:
                return None
            return _dicts(cur, [row])[0]

    async def execute(self, sql: str, params: tuple | list = ()) -> int:
        """Ichki (lock holdagi) ishga tushirish — tranzaksiya tashqarisida."""
        conn = self._require()
        async with self._lock:
            cur = await conn.execute(sql, params)
            return cur.rowcount

    # Tranzaksiya ichida ishlatiladigan versiyalar (lock qayta olinmaydi)
    @staticmethod
    async def _all(conn: aiosqlite.Connection, sql: str, params: tuple | list = ()) -> list[dict]:
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
        return _dicts(cur, rows)

    @staticmethod
    async def _one(conn: aiosqlite.Connection, sql: str, params: tuple | list = ()) -> dict | None:
        cur = await conn.execute(sql, params)
        row = await cur.fetchone()
        if row is None:
            return None
        return _dicts(cur, [row])[0]

    # ------------------------------------------------------- ulanish / sxema
    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = await aiosqlite.connect(self.path, isolation_level=None)
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA busy_timeout=10000")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.init_schema()
        log.info("Ma'lumotlar bazasi ulandi: %s", self.path.name)

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None
            log.info("Ma'lumotlar bazasi yopildi.")

    async def init_schema(self) -> None:
        conn = self._require()
        async with self._lock:
            await conn.executescript(SCHEMA)
            # Standart sozlamalar (borini o'zgartirmaymiz)
            for key, value in DEFAULT_SETTINGS.items():
                await conn.execute(
                    "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES(?, ?, ?)",
                    (key, value, now_iso()),
                )
            # Mahsulotlar bo'sh bo'lsa — standart katalogni yaratamiz
            cur = await conn.execute("SELECT COUNT(*) AS c FROM products")
            row = _dicts(cur, await cur.fetchall())
            if not row or int(row[0]["c"]) == 0:
                for item in SEED_PRODUCTS:
                    await conn.execute(
                        "INSERT INTO products(ptype, name, price, meta, sort_order,"
                        " is_active, created_at, updated_at) VALUES(?, ?, 0, ?, ?, 1, ?, ?)",
                        (
                            item["ptype"],
                            item["name"],
                            json.dumps(item.get("meta", {}), ensure_ascii=False),
                            item.get("sort", 0),
                            now_iso(),
                            now_iso(),
                        ),
                    )
                log.info("Standart mahsulotlar katalogi yaratildi (narxlar admin tomonidan belgilanadi).")

    # ------------------------------------------------------------- sozlamalar
    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = await self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        if row is None:
            return DEFAULT_SETTINGS.get(key, default)
        return row["value"]

    async def get_int_setting(self, key: str, default: int = 0) -> int:
        raw = await self.get_setting(key)
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return default

    async def get_settings(self, prefix: str = "") -> dict[str, str]:
        if prefix:
            rows = await self.fetchall(
                "SELECT key, value FROM settings WHERE key LIKE ? ORDER BY key", (prefix + "%",)
            )
        else:
            rows = await self.fetchall("SELECT key, value FROM settings ORDER BY key")
        return {r["key"]: r["value"] for r in rows}

    async def set_setting(self, key: str, value: Any) -> None:
        async with self._tx() as conn:
            await conn.execute(
                "INSERT INTO settings(key, value, updated_at) VALUES(?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                " updated_at = excluded.updated_at",
                (key, str(value), now_iso()),
            )

    # ---------------------------------------------------------------- users
    async def get_user(self, telegram_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str = "",
        referred_by: int | None = None,
    ) -> tuple[dict, bool]:
        """Foydalanuvchini topadi yoki yaratadi. Returns: (user, is_new)."""
        async with self._tx() as conn:
            row = await self._one(conn, "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            if row:
                # username/full_name'ni eng oxirgi holatga yangilaymiz
                await conn.execute(
                    "UPDATE users SET username = ?, full_name = ? WHERE telegram_id = ?",
                    (username, full_name, telegram_id),
                )
                row["username"] = username
                row["full_name"] = full_name
                return row, False

            cur = await conn.execute(
                "INSERT INTO users(telegram_id, username, full_name, balance, lang,"
                " referred_by, created_at) VALUES(?, ?, ?, 0, 'uz', ?, ?)",
                (telegram_id, username, full_name, referred_by, now_iso()),
            )
            _ = cur.lastrowid
            created = await self._one(conn, "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            return created or {}, True

    async def update_user(self, telegram_id: int, **fields: Any) -> None:
        allowed = {"username", "full_name", "lang", "is_banned"}
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return
        sets = ", ".join(f"{k} = ?" for k in clean)
        await self.execute(f"UPDATE users SET {sets} WHERE telegram_id = ?", (*clean.values(), telegram_id))

    async def add_balance(
        self,
        telegram_id: int,
        delta: int,
        ttype: str,
        note: str = "",
        ref_id: int | None = None,
        allow_negative: bool = False,
    ) -> int:
        """Balansni atomar o'zgartiradi. Yangi balansni qaytaradi.

        Kamaytirishda mablag' yetmasa — ValueError otadi (hech narsa o'zgarmaydi).
        """
        delta = int(delta)
        async with self._tx() as conn:
            user = await self._one(conn, "SELECT telegram_id, balance FROM users WHERE telegram_id = ?", (telegram_id,))
            if user is None:
                raise ValueError("Bunday foydalanuvchi topilmadi")
            new_balance = int(user["balance"]) + delta
            if new_balance < 0 and not allow_negative:
                raise ValueError("Balans mablag'i yetarli emas")

            await conn.execute(
                "UPDATE users SET balance = ? WHERE telegram_id = ?",
                (new_balance, telegram_id),
            )
            await conn.execute(
                "INSERT INTO transactions(user_id, ttype, amount, balance_after, ref_id, note, created_at)"
                " VALUES(?, ?, ?, ?, ?, ?, ?)",
                (telegram_id, ttype, delta, new_balance, ref_id, note, now_iso()),
            )
            return new_balance

    async def bump_user_counter(self, telegram_id: int, field: str, value: int = 1) -> None:
        allowed = {"referrals_count", "referral_bonus_total", "promo_bonus_total", "orders_count"}
        if field not in allowed:
            raise ValueError(f"Ruxsat etilmagan hisoblagich: {field}")
        await self.execute(
            f"UPDATE users SET {field} = {field} + ? WHERE telegram_id = ?",
            (int(value), telegram_id),
        )

    async def count_users(self) -> int:
        row = await self.fetchone("SELECT COUNT(*) AS c FROM users")
        return int(row["c"]) if row else 0

    async def list_recent_users(self, limit: int = 10) -> list[dict]:
        return await self.fetchall("SELECT * FROM users ORDER BY id DESC LIMIT ?", (limit,))

    async def list_user_ids(self) -> list[int]:
        rows = await self.fetchall("SELECT telegram_id FROM users ORDER BY id ASC")
        return [int(r["telegram_id"]) for r in rows]

    async def set_banned(self, telegram_id: int, banned: bool) -> None:
        await self.execute(
            "UPDATE users SET is_banned = ? WHERE telegram_id = ?",
            (1 if banned else 0, telegram_id),
        )

    # ------------------------------------------------------------- products
    async def list_products(self, ptype: str, active_only: bool = True) -> list[dict]:
        if active_only:
            return await self.fetchall(
                "SELECT * FROM products WHERE ptype = ? AND is_active = 1 ORDER BY sort_order, id",
                (ptype,),
            )
        return await self.fetchall(
            "SELECT * FROM products WHERE ptype = ? ORDER BY sort_order, id", (ptype,)
        )

    async def get_product(self, product_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM products WHERE id = ?", (product_id,))

    async def add_product(
        self,
        ptype: str,
        name: str,
        price: int = 0,
        meta: dict | None = None,
        image_file_id: str | None = None,
        description: str = "",
    ) -> int:
        async with self._tx() as conn:
            cur = await conn.execute(
                "INSERT INTO products(ptype, name, description, price, meta, image_file_id,"
                " is_active, sort_order, created_at, updated_at)"
                " VALUES(?, ?, ?, ?, ?, ?, 1, 99, ?, ?)",
                (
                    ptype,
                    name,
                    description,
                    int(price),
                    json.dumps(meta or {}, ensure_ascii=False),
                    image_file_id,
                    now_iso(),
                    now_iso(),
                ),
            )
            return int(cur.lastrowid or 0)

    async def update_product(self, product_id: int, **fields: Any) -> None:
        allowed = {"name", "description", "price", "meta", "image_file_id", "is_active", "sort_order"}
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            return
        if "meta" in clean and not isinstance(clean["meta"], str):
            clean["meta"] = json.dumps(clean["meta"], ensure_ascii=False)
        sets = ", ".join(f"{k} = ?" for k in clean)
        await self.execute(
            f"UPDATE products SET {sets}, updated_at = ? WHERE id = ?",
            (*clean.values(), now_iso(), product_id),
        )

    async def count_products_without_price(self) -> int:
        row = await self.fetchone(
            "SELECT COUNT(*) AS c FROM products WHERE is_active = 1 AND price <= 0"
            " AND meta NOT LIKE '%\"custom\": true%'"
        )
        return int(row["c"]) if row else 0

    # --------------------------------------------------------------- orders
    async def create_order(
        self,
        user_id: int,
        ptype: str,
        product_name: str,
        amount: int,
        product_id: int | None = None,
        details: dict | None = None,
        order_no: str | None = None,
    ) -> dict:
        import random
        import time

        async with self._tx() as conn:
            no = order_no
            if not no:
                while True:
                    no = f"XG-{int(time.time()) % 1000000:06d}-{random.randint(100, 999)}"
                    exists = await self._one(conn, "SELECT id FROM orders WHERE order_no = ?", (no,))
                    if not exists:
                        break
            cur = await conn.execute(
                "INSERT INTO orders(order_no, user_id, product_id, ptype, product_name, amount,"
                " status, details, created_at, updated_at)"
                " VALUES(?, ?, ?, ?, ?, ?, 'awaiting_payment', ?, ?, ?)",
                (
                    no,
                    user_id,
                    product_id,
                    ptype,
                    product_name,
                    int(amount),
                    json.dumps(details or {}, ensure_ascii=False),
                    now_iso(),
                    now_iso(),
                ),
            )
            order_id = int(cur.lastrowid or 0)
            await conn.execute(
                "UPDATE users SET orders_count = orders_count + 1 WHERE telegram_id = ?", (user_id,)
            )
            row = await self._one(conn, "SELECT * FROM orders WHERE id = ?", (order_id,))
            return row or {}

    async def get_order(self, order_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM orders WHERE id = ?", (order_id,))

    async def get_order_by_no(self, order_no: str) -> dict | None:
        return await self.fetchone("SELECT * FROM orders WHERE order_no = ?", (order_no,))

    async def list_user_orders(self, user_id: int, limit: int = 15) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        )

    async def list_orders_by_status(self, status: str, limit: int = 20) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit)
        )

    async def list_recent_orders(self, limit: int = 15) -> list[dict]:
        return await self.fetchall("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))

    async def set_order_status(self, order_id: int, status: str, paid_via: str | None = None,
                               admin_note: str | None = None) -> bool:
        if status not in ORDER_STATUSES:
            raise ValueError("Noto'g'ri buyurtma holati")
        sets = "status = ?, updated_at = ?"
        params: list[Any] = [status, now_iso()]
        if paid_via is not None:
            sets += ", paid_via = ?"
            params.append(paid_via)
        if admin_note is not None:
            sets += ", admin_note = ?"
            params.append(admin_note)
        params.append(order_id)
        n = await self.execute(f"UPDATE orders SET {sets} WHERE id = ?", tuple(params))
        return n > 0

    async def count_orders(self, status: str | None = None, user_id: int | None = None) -> int:
        sql, params = "SELECT COUNT(*) AS c FROM orders", []
        conds = []
        if status:
            conds.append("status = ?")
            params.append(status)
        if user_id:
            conds.append("user_id = ?")
            params.append(user_id)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        row = await self.fetchone(sql, tuple(params))
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------- payments
    async def create_payment(
        self,
        user_id: int,
        method: str,
        amount: int,
        receipt_key: str | None = None,
        receipt_ref: str | None = None,
    ) -> int | None:
        """Yangi to'lov yaratadi. receipt_key takrorlansa — None qaytaradi."""
        try:
            async with self._tx() as conn:
                cur = await conn.execute(
                    "INSERT INTO payments(user_id, method, amount, receipt_key, receipt_ref,"
                    " status, created_at) VALUES(?, ?, ?, ?, ?, 'pending', ?)",
                    (user_id, method, int(amount), receipt_key, receipt_ref, now_iso()),
                )
                return int(cur.lastrowid or 0)
        except sqlite3.IntegrityError:
            log.warning("Takroriy chek rad etildi (user=%s)", user_id)
            return None

    async def get_payment(self, payment_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))

    async def list_pending_payments(self, limit: int = 20) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM payments WHERE status = 'pending' ORDER BY id DESC LIMIT ?", (limit,)
        )

    async def has_receipt_key(self, receipt_key: str) -> bool:
        row = await self.fetchone("SELECT id FROM payments WHERE receipt_key = ?", (receipt_key,))
        return row is not None

    async def attach_receipt(self, payment_id: int, receipt_key: str, receipt_ref: str) -> str | None:
        """Chekni to'lovga bog'laydi. None = muvaffaqiyatli.

        Agar shu chek boshqa to'lovda ishlatilgan bo'lsa yoki to'lov allaqachon
        ko'rib chiqilgan bo'lsa — xato sababini qaytaradi.
        """
        try:
            async with self._tx() as conn:
                payment = await self._one(conn, "SELECT * FROM payments WHERE id = ?", (payment_id,))
                if payment is None:
                    return "To'lov topilmadi"
                if payment["status"] != "pending":
                    return "Bu to'lov allaqachon ko'rib chiqilgan"
                if payment["receipt_key"]:
                    return "Chek allaqachon yuborilgan"
                dup = await self._one(conn, "SELECT id FROM payments WHERE receipt_key = ?", (receipt_key,))
                if dup:
                    return "Bu chek oldin ishlatilgan"
                await conn.execute(
                    "UPDATE payments SET receipt_key = ?, receipt_ref = ? WHERE id = ?",
                    (receipt_key, receipt_ref, payment_id),
                )
                return None
        except sqlite3.IntegrityError:
            return "Bu chek oldin ishlatilgan"

    async def approve_payment(self, payment_id: int, admin_id: int) -> tuple[bool, str]:
        """Chekni tasdiqlash — balans bir marta oshadi."""
        async with self._tx() as conn:
            payment = await self._one(conn, "SELECT * FROM payments WHERE id = ?", (payment_id,))
            if payment is None:
                return False, "To'lov topilmadi"
            if payment["status"] != "pending":
                return False, f"Bu to'lov allaqachon {PAYMENT_STATUSES.get(payment['status'], payment['status'])}"

            user = await self._one(conn, "SELECT * FROM users WHERE telegram_id = ?", (payment["user_id"],))
            if user is None:
                return False, "Foydalanuvchi topilmadi"

            new_balance = int(user["balance"]) + int(payment["amount"])
            await conn.execute(
                "UPDATE payments SET status = 'approved', admin_id = ?, processed_at = ? WHERE id = ?",
                (admin_id, now_iso(), payment_id),
            )
            await conn.execute(
                "UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, payment["user_id"])
            )
            await conn.execute(
                "INSERT INTO transactions(user_id, ttype, amount, balance_after, ref_id, note, created_at)"
                " VALUES(?, 'topup', ?, ?, ?, ?, ?)",
                (
                    payment["user_id"],
                    int(payment["amount"]),
                    new_balance,
                    payment_id,
                    f"Hisob to'ldirildi ({payment['method']})",
                    now_iso(),
                ),
            )
            return True, new_balance

    async def reject_payment(self, payment_id: int, admin_id: int, note: str = "") -> tuple[bool, str]:
        async with self._tx() as conn:
            payment = await self._one(conn, "SELECT * FROM payments WHERE id = ?", (payment_id,))
            if payment is None:
                return False, "To'lov topilmadi"
            if payment["status"] != "pending":
                return False, f"Bu to'lov allaqachon {PAYMENT_STATUSES.get(payment['status'], payment['status'])}"
            await conn.execute(
                "UPDATE payments SET status = 'rejected', admin_id = ?, note = ?, processed_at = ?"
                " WHERE id = ?",
                (admin_id, note[:200], now_iso(), payment_id),
            )
            return True, "Rad etildi"

    async def credit_charge(
        self,
        charge_id: str,
        user_id: int,
        amount_uzs: int,
        stars: int,
        method: str = "telegram_stars",
    ) -> int | None:
        """Telegram Stars to'lovini bir marta hisobga oshiradi (charge_id unikalligi)."""
        try:
            async with self._tx() as conn:
                user = await self._one(conn, "SELECT * FROM users WHERE telegram_id = ?", (user_id,))
                if user is None:
                    return None
                new_balance = int(user["balance"]) + int(amount_uzs)
                cur = await conn.execute(
                    "INSERT INTO payments(user_id, method, amount, status, tg_charge_id,"
                    " receipt_ref, processed_at, created_at)"
                    " VALUES(?, ?, ?, 'approved', ?, ?, ?, ?)",
                    (
                        user_id,
                        method,
                        int(amount_uzs),
                        charge_id,
                        f"{stars} ⭐",
                        now_iso(),
                        now_iso(),
                    ),
                )
                payment_id = int(cur.lastrowid or 0)
                await conn.execute(
                    "UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, user_id)
                )
                await conn.execute(
                    "INSERT INTO transactions(user_id, ttype, amount, balance_after, ref_id, note, created_at)"
                    " VALUES(?, 'topup', ?, ?, ?, ?, ?)",
                    (user_id, int(amount_uzs), new_balance, payment_id, f"Telegram Stars orqali ({stars} ⭐)", now_iso()),
                )
                return payment_id
        except sqlite3.IntegrityError:
            log.warning("Takroriy Telegram to'lov (charge) e'tiborsiz qoldirildi: user=%s", user_id)
            return None

    # ---------------------------------------------------------- transactions
    async def list_user_transactions(self, user_id: int, limit: int = 20) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        )

    async def total_balance(self) -> int:
        row = await self.fetchone("SELECT COALESCE(SUM(balance), 0) AS s FROM users")
        return int(row["s"]) if row else 0

    async def total_revenue(self) -> int:
        """Buyurtmalar uchun yechilgan pul (purchase + refund hisobga olinadi)."""
        row = await self.fetchone(
            "SELECT COALESCE(SUM(CASE WHEN ttype = 'purchase' THEN amount"
            " WHEN ttype = 'refund' THEN amount ELSE 0 END), 0) AS s FROM transactions"
        )
        return int(row["s"]) if row else 0

    # ------------------------------------------------------------ promo kod
    async def create_promo(
        self,
        code: str,
        bonus: int,
        description: str = "",
        expires_at: str | None = None,
        max_uses: int = 0,
        per_user_limit: int = 1,
    ) -> int:
        async with self._tx() as conn:
            cur = await conn.execute(
                "INSERT INTO promo_codes(code, bonus, description, expires_at, max_uses,"
                " per_user_limit, is_active, created_at) VALUES(?, ?, ?, ?, ?, ?, 1, ?)",
                (code, int(bonus), description, expires_at, int(max_uses), int(per_user_limit), now_iso()),
            )
            return int(cur.lastrowid or 0)

    async def get_promo(self, promo_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM promo_codes WHERE id = ?", (promo_id,))

    async def get_promo_by_code(self, code: str) -> dict | None:
        return await self.fetchone("SELECT * FROM promo_codes WHERE code = ?", (code,))

    async def list_promos(self, limit: int = 30) -> list[dict]:
        return await self.fetchall("SELECT * FROM promo_codes ORDER BY id DESC LIMIT ?", (limit,))

    async def set_promo_active(self, promo_id: int, active: bool) -> None:
        await self.execute(
            "UPDATE promo_codes SET is_active = ? WHERE id = ?",
            (1 if active else 0, promo_id),
        )

    async def delete_promo(self, promo_id: int) -> None:
        async with self._tx() as conn:
            await conn.execute("DELETE FROM promo_usages WHERE code_id = ?", (promo_id,))
            await conn.execute("DELETE FROM promo_codes WHERE id = ?", (promo_id,))

    async def promo_usage_count(self, promo_id: int, user_id: int | None = None) -> int:
        if user_id is None:
            row = await self.fetchone("SELECT COUNT(*) AS c FROM promo_usages WHERE code_id = ?", (promo_id,))
        else:
            row = await self.fetchone(
                "SELECT COUNT(*) AS c FROM promo_usages WHERE code_id = ? AND user_id = ?",
                (promo_id, user_id),
            )
        return int(row["c"]) if row else 0

    async def use_promo(self, code: str, user_id: int) -> tuple[bool, int, str]:
        """Promo-kodni qo'llash (atomar).

        Returns: (muvaffaqiyat, bonus, xabar)
        Bir koddan takroriy bonus olish bloklangan.
        """
        async with self._tx() as conn:
            promo = await self._one(conn, "SELECT * FROM promo_codes WHERE code = ?", (code,))
            if promo is None:
                return False, 0, "Bunday promo-kod topilmadi"
            if not int(promo["is_active"]):
                return False, 0, "Bu promo-kod o'chirilgan"

            today = now_iso()[:10]
            if promo["expires_at"] and str(promo["expires_at"])[:10] < today:
                return False, 0, "Bu promo-kod muddati tugagan"

            total_uses = await self._one(
                conn, "SELECT COUNT(*) AS c FROM promo_usages WHERE code_id = ?", (promo["id"],)
            )
            used = int(total_uses["c"]) if total_uses else 0
            if int(promo["max_uses"]) > 0 and used >= int(promo["max_uses"]):
                return False, 0, "Bu kod bo'yicha limit tugagan"

            my_uses = await self._one(
                conn,
                "SELECT COUNT(*) AS c FROM promo_usages WHERE code_id = ? AND user_id = ?",
                (promo["id"], user_id),
            )
            mine = int(my_uses["c"]) if my_uses else 0
            if mine >= int(promo["per_user_limit"]):
                return False, 0, "Siz bu kodni allaqachon ishlatgansiz"

            user = await self._one(conn, "SELECT * FROM users WHERE telegram_id = ?", (user_id,))
            if user is None:
                return False, 0, "Foydalanuvchi topilmadi"

            bonus = int(promo["bonus"])
            new_balance = int(user["balance"]) + bonus

            await conn.execute(
                "INSERT INTO promo_usages(code_id, user_id, amount, used_at) VALUES(?, ?, ?, ?)",
                (promo["id"], user_id, bonus, now_iso()),
            )
            await conn.execute(
                "UPDATE promo_codes SET used_count = used_count + 1 WHERE id = ?", (promo["id"],)
            )
            await conn.execute(
                "UPDATE users SET balance = ?, promo_bonus_total = promo_bonus_total + ?"
                " WHERE telegram_id = ?",
                (new_balance, bonus, user_id),
            )
            await conn.execute(
                "INSERT INTO transactions(user_id, ttype, amount, balance_after, ref_id, note, created_at)"
                " VALUES(?, 'promo', ?, ?, ?, ?, ?)",
                (user_id, bonus, new_balance, promo["id"], f"Promo-kod: {code}", now_iso()),
            )
            return True, bonus, "ok"

    # ----------------------------------------------------------- referallar
    async def add_referral(self, referrer_id: int, referred_id: int) -> tuple[bool, str]:
        if referrer_id == referred_id:
            return False, "O'zini o'zi taklif qilib bo'lmaydi"
        exists = await self.fetchone("SELECT id FROM referrals WHERE referred_id = ?", (referred_id,))
        if exists:
            return False, "Bu foydalanuvchi allaqachon taklif qilingan"
        try:
            async with self._tx() as conn:
                await conn.execute(
                    "INSERT INTO referrals(referrer_id, referred_id, status, created_at)"
                    " VALUES(?, ?, 'pending', ?)",
                    (referrer_id, referred_id, now_iso()),
                )
            return True, "ok"
        except sqlite3.IntegrityError:
            return False, "Bu foydalanuvchi allaqachon taklif qilingan"

    async def get_referral_by_user(self, referred_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM referrals WHERE referred_id = ?", (referred_id,))

    async def activate_referral(self, referred_id: int) -> tuple[bool, int | None]:
        """Taklifni faollashtirib, refererga bir marta bonus beradi.

        Returns: (berildi_mi, referrer_id)
        """
        async with self._tx() as conn:
            ref = await self._one(conn, "SELECT * FROM referrals WHERE referred_id = ?", (referred_id,))
            if ref is None or ref["status"] != "pending":
                return False, None

            referrer = await self._one(
                conn, "SELECT * FROM users WHERE telegram_id = ?", (ref["referrer_id"],)
            )
            if referrer is None:
                await conn.execute(
                    "UPDATE referrals SET status = 'active', activated_at = ? WHERE id = ?",
                    (now_iso(), ref["id"]),
                )
                return False, None

            # Bonus narxi (so'm) — sozlamadan olinadi
            bonus_row = await self._one(conn, "SELECT value FROM settings WHERE key = 'referral_bonus'")
            try:
                bonus = int(bonus_row["value"]) if bonus_row else 0
            except (TypeError, ValueError):
                bonus = 0

            new_balance = int(referrer["balance"]) + bonus
            await conn.execute(
                "UPDATE referrals SET status = 'active', bonus = ?, activated_at = ? WHERE id = ?",
                (bonus, now_iso(), ref["id"]),
            )
            if bonus:
                await conn.execute(
                    "UPDATE users SET balance = ?, referrals_count = referrals_count + 1,"
                    " referral_bonus_total = referral_bonus_total + ? WHERE telegram_id = ?",
                    (new_balance, bonus, ref["referrer_id"]),
                )
                await conn.execute(
                    "INSERT INTO transactions(user_id, ttype, amount, balance_after, ref_id, note, created_at)"
                    " VALUES(?, 'bonus', ?, ?, ?, ?, ?)",
                    (ref["referrer_id"], bonus, new_balance, ref["id"], "Taklif bonusi", now_iso()),
                )
            else:
                await conn.execute(
                    "UPDATE users SET referrals_count = referrals_count + 1 WHERE telegram_id = ?",
                    (ref["referrer_id"],),
                )
            return True, int(ref["referrer_id"])

    async def referral_stats(self) -> dict:
        total = await self.fetchone("SELECT COUNT(*) AS c FROM referrals")
        active = await self.fetchone("SELECT COUNT(*) AS c FROM referrals WHERE status = 'active'")
        paid = await self.fetchone("SELECT COALESCE(SUM(bonus), 0) AS s FROM referrals WHERE status = 'active'")
        return {
            "total": int(total["c"]) if total else 0,
            "active": int(active["c"]) if active else 0,
            "paid": int(paid["s"]) if paid else 0,
        }

    # ------------------------------------------------------------ admin log
    async def add_log(self, admin_id: int, action: str, details: str = "") -> None:
        try:
            await self.execute(
                "INSERT INTO admin_logs(admin_id, action, details, created_at) VALUES(?, ?, ?, ?)",
                (int(admin_id), action[:100], details[:500], now_iso()),
            )
        except Exception as exc:  # log yozuvi uchun botni to'xtatmaymiz
            log.warning("Admin jurnaliga yozib bo'lmadi: %s", exc)

    async def recent_logs(self, limit: int = 20) -> list[dict]:
        return await self.fetchall("SELECT * FROM admin_logs ORDER BY id DESC LIMIT ?", (limit,))

    # --------------------------------------------------------------- stats
    async def general_stats(self) -> dict:
        users = await self.count_users()
        orders_total = await self.count_orders()
        by_status = {}
        for status in ORDER_STATUSES:
            by_status[status] = await self.count_orders(status=status)
        pending = await self.fetchone("SELECT COUNT(*) AS c FROM payments WHERE status = 'pending'")
        revenue = await self.total_revenue()
        balance = await self.total_balance()
        referrals = await self.referral_stats()
        products_no_price = await self.count_products_without_price()
        return {
            "users": users,
            "orders_total": orders_total,
            "orders_by_status": by_status,
            "pending_payments": int(pending["c"]) if pending else 0,
            "revenue": revenue,
            "total_balance": balance,
            "referrals": referrals,
            "products_without_price": products_no_price,
        }


# Botning bitta umumiy bazasi (barcha modullar shuni import qiladi)
db = Database()

__all__ = [
    "Database",
    "db",
    "ORDER_STATUSES",
    "PAYMENT_STATUSES",
    "PTYPE_STARS",
    "PTYPE_PREMIUM",
    "PTYPE_GIFT",
    "PTYPES",
    "DEFAULT_SETTINGS",
    "now_iso",
]
