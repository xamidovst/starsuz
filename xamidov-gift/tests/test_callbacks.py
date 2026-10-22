"""Klaviatura callback data lari handler kutilgan formatda ekanini tekshiradi."""

from __future__ import annotations

from database import PTYPE_STARS
from keyboards.inline import (
    admin_methods_kb,
    admin_orders_kb,
    admin_products_kb,
    admin_promo_kb,
    admin_settings_kb,
    order_actions_kb,
    orders_list_kb,
    products_kb,
    topup_methods_kb,
)


def _callbacks(kb) -> list[str]:
    return [btn.callback_data for row in kb.inline_keyboard for btn in row if btn.callback_data]


def test_products_kb():
    products = [{"id": 5, "name": "50 Stars", "price": 25_000, "meta": "{}", "ptype": PTYPE_STARS}]
    datas = _callbacks(products_kb(PTYPE_STARS, products))
    assert "stars:buy:5" in datas
    # handler: callback.data.split(":")[-1] → "5"
    assert datas[datas.index("stars:buy:5")].split(":")[-1] == "5"


def test_order_actions_kb():
    datas = _callbacks(order_actions_kb("XG-123456-789"))
    assert "pay:XG-123456-789" in datas
    assert "cancel:XG-123456-789" in datas
    assert "myorders" in datas


def test_orders_list_kb():
    orders = [{"order_no": "XG-000001-111", "status": "pending"}]
    datas = _callbacks(orders_list_kb(orders))
    assert "order:XG-000001-111" in datas


def test_topup_kb():
    methods = [{"id": "uzcard", "name": "UzCard", "details": "8600", "active": True}]
    datas = _callbacks(topup_methods_kb(methods))
    assert "topup:uzcard" in datas
    assert "topup:stars" in datas


def test_admin_products_kb():
    products = [{"id": 7, "name": "Rose", "price": 0, "meta": "{}", "is_active": 1}]
    datas = _callbacks(admin_products_kb("gift", products))
    assert "adm:pr:gift:p7" in datas
    parts = datas[datas.index("adm:pr:gift:p7")].split(":")
    assert len(parts) == 4 and parts[3] == "p7"


def test_admin_orders_kb():
    orders = [{"order_no": "XG-1", "status": "pending", "id": 9}]
    datas = _callbacks(admin_orders_kb(orders))
    assert "adm:o:9" in datas
    assert "adm:ol:completed" in datas
    assert datas[datas.index("adm:ol:completed")].split(":")[-1] == "completed"


def test_admin_promo_kb():
    promos = [{"id": 3, "code": "TEST", "bonus": 1000, "is_active": 1}]
    datas = _callbacks(admin_promo_kb(promos))
    assert "adm:pc:3" in datas
    assert "adm:pc:new" in datas


def test_admin_settings_kb_keys():
    datas = _callbacks(admin_settings_kb())
    keys = [d.split(":")[-1] for d in datas if d.startswith("adm:edit:")]
    assert "referral_bonus" in keys
    assert "stars_topup_rate" in keys
    # settings handler allowed ro'yxati bilan mos
    from keyboards.inline import SETTING_ROWS

    allowed = {k for k, _, _ in SETTING_ROWS}
    assert set(keys) <= allowed


def test_admin_methods_kb():
    methods = [{"id": "click", "name": "Click", "details": "", "active": True}]
    datas = _callbacks(admin_methods_kb(methods))
    assert "adm:paym:click" in datas
    assert "adm:paym:new" in datas
