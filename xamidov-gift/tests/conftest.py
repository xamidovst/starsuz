"""Test muhiti: har bir test alohida vaqtinchalik baza bilan ishlaydi."""

from __future__ import annotations

import pytest

from database import Database


@pytest.fixture
async def db(tmp_path):
    """Vaqtinchalik SQLite baza (test tugagach o'chiriladi)."""
    database = Database(tmp_path / "test.db")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
async def svc_db(db, monkeypatch):
    """Xizmat modullari test bazasini ishlatishi uchun (singleton almashtiriladi)."""
    from services import order_service, payment_service, referral_service

    monkeypatch.setattr(order_service, "db", db)
    monkeypatch.setattr(payment_service, "db", db)
    monkeypatch.setattr(referral_service, "db", db)
    return db
