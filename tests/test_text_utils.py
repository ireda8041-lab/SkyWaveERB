from __future__ import annotations

from core.text_utils import normalize_user_text


def test_normalize_user_text_collapses_repeats():
    assert normalize_user_text("غلططططططط") == "غلط"


def test_normalize_user_text_fixes_common_phrase():
    assert normalize_user_text("بيانات غلططططط") == "بيانات غير صحيحة"


def test_normalize_user_text_trims_and_collapses_spaces():
    assert normalize_user_text("  مرحبا   بك  ") == "مرحبا بك"
