"""Xizmatlar testlari: buyurtma to'lash, bekor qilish, referal bonus, to'lov."""

from __future__ import annotations

import pytest

from database import PTYPE_STARS
from services import order_service, payment_service, referral_service


async def _prepare_user(db, user_id: int, balance: int = 0):
    await db.get_or_create_user(user_id, f"user{user_id}", f"Foydalanuvchi {user_id}")
    if balance:
        await db.add_balance(user_id, balance, "topup", "test boshi")
    return await db.get_user(user_id)


# ------------------------------------------------------------- buyurtma to'lash
async def test_pay_with_balance_success(svc_db):
    await _prepare_user(svc_db, 1, 100_000)
    order = await order_service.create_order(1, PTYPE_STARS, "50 Stars", 25_000, details={"stars": 50})

    ok, updated, text = await order_service.pay_with_balance(order["order_no"], 1)
    assert ok is True
    assert updated["status"] == "pending"
    assert updated["paid_via"] == "balance"

    user = await svc_db.get_user(1)
    assert user["balance"] == 75_000


async def test_pay_insufficient_balance(svc_db):
    await _prepare_user(svc_db, 2, 1_000)
    order = await order_service.create_order(2, PTYPE_STARS, "50 Stars", 25_000)

    ok, _, text = await order_service.pay_with_balance(order["order_no"], 2)
    assert ok is False
    assert "yetarli" in text.lower()

    user = await svc_db.get_user(2)
    assert user["balance"] == 1_000, "Balans o'zgarmasligi kerak"
    fresh = await svc_db.get_order(order["id"])
    assert fresh["status"] == "awaiting_payment"


async def test_order_of_other_user_rejected(svc_db):
    await _prepare_user(svc_db, 3, 50_000)
    await _prepare_user(svc_db, 4)
    order = await order_service.create_order(3, PTYPE_STARS, "50 Stars", 25_000)

    ok, _, text = await order_service.pay_with_balance(order["order_no"], 4)
    assert ok is False
    assert "tegishli" in text.lower()


async def test_zero_price_order_blocked(svc_db):
    await _prepare_user(svc_db, 5, 10_000)
    with pytest.raises(order_service.OrderError):
        await order_service.create_order(5, PTYPE_STARS, "Boshqa miqdor", 0)


async def test_cancel_with_refund(svc_db):
    await _prepare_user(svc_db, 6, 60_000)
    order = await order_service.create_order(6, PTYPE_STARS, "50 Stars", 25_000)
    await order_service.pay_with_balance(order["order_no"], 6)

    ok, _, text = await order_service.cancel_order(order["order_no"], 6)
    assert ok is True
    assert "qaytarildi" in text

    user = await svc_db.get_user(6)
    assert user["balance"] == 60_000


async def test_admin_reject_refunds(svc_db):
    await _prepare_user(svc_db, 7, 60_000)
    order = await order_service.create_order(7, PTYPE_STARS, "50 Stars", 25_000)
    await order_service.pay_with_balance(order["order_no"], 7)

    ok, text = await order_service.admin_change_status(order, "cancelled", admin_id=999)
    assert ok is True
    assert "qaytarildi" in text

    user = await svc_db.get_user(7)
    assert user["balance"] == 60_000

    logs = await svc_db.recent_logs(5)
    assert any(l["action"] == "order_status" for l in logs), "Admin amali jurnalga yozilishi kerak"


async def test_admin_complete_no_refund(svc_db):
    await _prepare_user(svc_db, 8, 60_000)
    order = await order_service.create_order(8, PTYPE_STARS, "50 Stars", 25_000)
    await order_service.pay_with_balance(order["order_no"], 8)

    ok, _ = await order_service.admin_change_status(order, "completed", admin_id=999)
    assert ok is True
    user = await svc_db.get_user(8)
    assert user["balance"] == 35_000, "Bajarilgan buyurtma uchun pul qaytmasligi kerak"


# ------------------------------------------------------------------ referal
async def test_referral_bonus_on_first_purchase(svc_db):
    await svc_db.set_setting("referral_bonus", "5000")
    await _prepare_user(svc_db, 10, 0)
    await _prepare_user(svc_db, 11, 60_000)
    ok, _ = await svc_db.add_referral(10, 11)
    assert ok is True

    order = await order_service.create_order(11, PTYPE_STARS, "50 Stars", 25_000)
    paid, _, _ = await order_service.pay_with_balance(order["order_no"], 11)
    assert paid is True

    referrer = await svc_db.get_user(10)
    assert referrer["balance"] == 5_000, "Referal bonusi birinchi xariddan keyin berilishi kerak"

    # Ikkinchi xarid uchun bonus qayta berilmaydi
    order2 = await order_service.create_order(11, PTYPE_STARS, "50 Stars", 25_000)
    await order_service.pay_with_balance(order2["order_no"], 11)
    referrer2 = await svc_db.get_user(10)
    assert referrer2["balance"] == 5_000


async def test_referral_link_and_parse():
    assert referral_service.parse_ref_arg("ref_123") == 123
    assert referral_service.parse_ref_arg("REF_123") == 123
    assert referral_service.parse_ref_arg("nonsense") is None
    assert referral_service.parse_ref_arg(None) is None


# ------------------------------------------------------------------ to'lovlar
async def test_topup_flow(svc_db):
    await _prepare_user(svc_db, 20)
    payment_id = await payment_service.create_topup_request(20, "Click", 40_000)
    assert payment_id is not None

    assert await payment_service.submit_receipt(payment_id, "f:key1", "key1") is None
    # Takroriy chek rad etiladi
    error = await payment_service.submit_receipt(payment_id + 100, "f:key1", "key1")
    assert error is not None

    ok, _, user_id = await payment_service.approve(payment_id, admin_id=999)
    assert ok is True and user_id == 20

    user = await svc_db.get_user(20)
    assert user["balance"] == 40_000

    # Ikkinchi tasdiqlash mumkin emas
    ok2, _, _ = await payment_service.approve(payment_id, admin_id=999)
    assert ok2 is False
    assert (await svc_db.get_user(20))["balance"] == 40_000


async def test_credit_stars_payment(svc_db):
    await _prepare_user(svc_db, 21)
    await svc_db.set_setting("stars_topup_rate", "500")

    ok, amount = await payment_service.credit_stars(21, 15, "ch-1")
    assert ok is True and amount == 7_500

    # Xuddi shu charge qayta ishlanmaydi
    ok2, _ = await payment_service.credit_stars(21, 15, "ch-1")
    assert ok2 is False

    user = await svc_db.get_user(21)
    assert user["balance"] == 7_500


def test_stars_payload_roundtrip():
    payload = payment_service.stars_payload(12345, 50)
    parsed = payment_service.parse_stars_payload(payload)
    assert parsed == (12345, 50)

    assert payment_service.parse_stars_payload("bad") is None
    assert payment_service.parse_stars_payload("topup:0:50") is None
    assert payment_service.parse_stars_payload("topup:12:999999") is None
