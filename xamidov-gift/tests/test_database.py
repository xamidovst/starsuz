"""Ma'lumotlar bazasi testlari: balans atomikligi, promo, to'lov, referal."""

from __future__ import annotations

import pytest

from database import PTYPE_STARS


# ------------------------------------------------------------------ boshlang'ich
async def test_schema_and_seed(db):
    stars = await db.list_products(PTYPE_STARS, active_only=False)
    assert stars, "Standart Stars kataligi yaratilishi kerak"
    assert any(p["meta"].find("custom") >= 0 for p in stars), "'Boshqa miqdor' mahsuloti bo'lishi kerak"


async def test_settings_defaults(db):
    assert await db.get_int_setting("referral_bonus") == 5000
    await db.set_setting("referral_bonus", "1234")
    assert await db.get_int_setting("referral_bonus") == 1234


# ----------------------------------------------------------------------- users
async def test_user_create_and_update(db):
    user, is_new = await db.get_or_create_user(111, "shax", "Shax Nomi")
    assert is_new is True
    assert user["balance"] == 0

    again, is_new2 = await db.get_or_create_user(111, "shax", "Shax Nomi")
    assert is_new2 is False
    assert again["id"] == user["id"]


async def test_balance_atomic(db):
    await db.get_or_create_user(222)
    await db.add_balance(222, 10_000, "topup", "test")

    # Mablag' yetarli emas — hech narsa o'zgarmaydi
    with pytest.raises(ValueError):
        await db.add_balance(222, -50_000, "purchase", "test")

    user = await db.get_user(222)
    assert user["balance"] == 10_000, "Muvaffaqiyatsiz urinish balansga ta'sir qilmasligi kerak"

    await db.add_balance(222, -4_000, "purchase", "test")
    user = await db.get_user(222)
    assert user["balance"] == 6_000

    txs = await db.list_user_transactions(222)
    assert [t["ttype"] for t in txs] == ["purchase", "topup"]  # oxirgi avval


async def test_banned_user(db):
    await db.get_or_create_user(333)
    await db.set_banned(333, True)
    user = await db.get_user(333)
    assert user["is_banned"] == 1


# ---------------------------------------------------------------------- orders
async def test_order_lifecycle(db):
    await db.get_or_create_user(444)
    order = await db.create_order(444, PTYPE_STARS, "100 Stars", 15_000, details={"stars": 100})
    assert order["status"] == "awaiting_payment"
    assert order["order_no"].startswith("XG-")

    ok = await db.set_order_status(order["id"], "pending", paid_via="balance")
    assert ok is True

    with pytest.raises(ValueError):
        await db.set_order_status(order["id"], "not-a-status")

    user = await db.get_user(444)
    assert user["orders_count"] == 1


# ----------------------------------------------------------------------- promo
async def test_promo_single_use_per_user(db):
    await db.get_or_create_user(555)
    await db.create_promo("TEST10", 5_000, max_uses=0, per_user_limit=1)

    ok, bonus, _ = await db.use_promo("TEST10", 555)
    assert ok is True and bonus == 5_000

    # Takroriy foydalanish taqiqlanadi
    ok2, _, msg2 = await db.use_promo("TEST10", 555)
    assert ok2 is False and "allaqachon" in msg2.lower()

    user = await db.get_user(555)
    assert user["balance"] == 5_000
    assert user["promo_bonus_total"] == 5_000


async def test_promo_limits(db):
    await db.get_or_create_user(556)
    await db.get_or_create_user(557)
    await db.create_promo("LIMIT2", 1_000, max_uses=2, per_user_limit=5)

    assert (await db.use_promo("LIMIT2", 556))[0] is True
    assert (await db.use_promo("LIMIT2", 557))[0] is True
    # Limit tugadi
    await db.get_or_create_user(558)
    ok, _, msg = await db.use_promo("LIMIT2", 558)
    assert ok is False and "limit" in msg.lower()


async def test_promo_unknown_code(db):
    await db.get_or_create_user(559)
    ok, _, _ = await db.use_promo("YOQ", 559)
    assert ok is False


# --------------------------------------------------------------------- payments
async def test_receipt_reuse_blocked(db):
    await db.get_or_create_user(666)
    first = await db.create_payment(666, "Click", 50_000)
    second = await db.create_payment(666, "Click", 50_000)
    assert first is not None and second is not None

    assert await db.attach_receipt(first, "f:abc", "abc") is None
    # Xuddi shu chek boshqa to'lovga biriktirilmaydi
    error = await db.attach_receipt(second, "f:abc", "abc")
    assert error is not None and "ishlatilgan" in error.lower()


async def test_approve_payment_only_once(db):
    await db.get_or_create_user(777)
    payment_id = await db.create_payment(777, "Payme", 20_000)
    await db.attach_receipt(payment_id, "f:xyz", "xyz")

    ok, new_balance = await db.approve_payment(payment_id, admin_id=1)
    assert ok is True and new_balance == 20_000

    # Ikkinchi marta tasdiqlab bo'lmaydi
    ok2, msg = await db.approve_payment(payment_id, admin_id=1)
    assert ok2 is False

    user = await db.get_user(777)
    assert user["balance"] == 20_000, "Balans ikki marta oshmasligi kerak"


async def test_reject_payment(db):
    await db.get_or_create_user(778)
    payment_id = await db.create_payment(778, "Click", 10_000)
    ok, _ = await db.reject_payment(payment_id, admin_id=1, note="chek noto'g'ri")
    assert ok is True
    user = await db.get_user(778)
    assert user["balance"] == 0


async def test_stars_charge_unique(db):
    await db.get_or_create_user(888)
    first = await db.credit_charge("charge-1", 888, 75_000, 15)
    assert first is not None
    # Xuddi shu charge qayta hisoblanmaydi
    second = await db.credit_charge("charge-1", 888, 75_000, 15)
    assert second is None
    user = await db.get_user(888)
    assert user["balance"] == 75_000


# ------------------------------------------------------------------- referrals
async def test_referral_rules(db):
    await db.get_or_create_user(900)
    await db.get_or_create_user(901)

    # O'zini o'zi taklif qilib bo'lmaydi
    ok, reason = await db.add_referral(900, 900)
    assert ok is False and "o'zi" in reason.lower()

    ok2, _ = await db.add_referral(900, 901)
    assert ok2 is True

    # Takroriy taklif qayd etilmaydi
    ok3, _ = await db.add_referral(902, 901)
    assert ok3 is False


async def test_referral_bonus_once(db):
    await db.get_or_create_user(910)
    await db.get_or_create_user(911)
    await db.set_setting("referral_bonus", "7000")
    await db.add_referral(910, 911)

    granted, referrer_id = await db.activate_referral(911)
    assert granted is True and referrer_id == 910

    referrer = await db.get_user(910)
    assert referrer["balance"] == 7_000
    assert referrer["referrals_count"] == 1

    # Ikkinchi marta bonus berilmaydi
    granted2, _ = await db.activate_referral(911)
    assert granted2 is False
    referrer2 = await db.get_user(910)
    assert referrer2["balance"] == 7_000


# ---------------------------------------------------------------------- stats
async def test_general_stats(db):
    await db.get_or_create_user(999)
    stats = await db.general_stats()
    assert stats["users"] == 1
    assert "orders_by_status" in stats
    assert stats["pending_payments"] == 0
