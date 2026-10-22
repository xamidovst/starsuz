"""Validatollar testlari."""

from __future__ import annotations

from utils.validators import (
    clean_line,
    clean_text,
    format_money,
    normalize_promo,
    parse_amount,
    parse_int,
    parse_tg_id,
)


def test_parse_amount():
    assert parse_amount("50000") == 50000
    assert parse_amount("50 000") == 50000
    assert parse_amount("50,000") == 50000
    assert parse_amount("0") is None
    assert parse_amount("-5") is None
    assert parse_amount("abc") is None
    assert parse_amount("") is None
    assert parse_amount(None) is None
    assert parse_amount("5", min_value=10) is None


def test_parse_int():
    assert parse_int("-10") == -10
    assert parse_int("0", 0, 100) == 0
    assert parse_int("101", 0, 100) is None
    assert parse_int("1.5") is None


def test_parse_tg_id():
    assert parse_tg_id("12345") == 12345
    assert parse_tg_id("@username") is None
    assert parse_tg_id("-5") is None
    assert parse_tg_id(777) == 777


def test_normalize_promo():
    assert normalize_promo(" abc123 ") == "ABC123"
    assert normalize_promo("yaxshi-kod_1") == "YAXSHI-KOD_1"
    assert normalize_promo("ab") is None
    assert normalize_promo("bo'sh joy") is None
    assert normalize_promo(None) is None


def test_format_money():
    assert format_money(125000) == "125 000 so'm"
    assert format_money(0) == "0 so'm"


def test_clean_text():
    assert clean_text("  salom \r\n dunyo  ") == "salom \n dunyo"
    assert len(clean_text("x" * 1000, max_len=10)) <= 11
    assert clean_line("bir\nikki") == "bir ikki"
