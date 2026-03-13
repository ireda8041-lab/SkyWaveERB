from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
# Collapse noisy repeated letters only. Numeric/account references like 111001
# must remain stable and must never be normalized into a different identifier.
_REPEAT_CHAR_RE = re.compile(r"([^\W\d_])\1{2,}", flags=re.DOTALL)
_REPEAT_PUNCT_RE = re.compile(r"([!؟,.،؛:])\1+")
_TATWEEL_RE = re.compile(r"ـ+")
_BAD_DATA_RE = re.compile(r"بيانات\s+غلط+", flags=re.IGNORECASE)


def normalize_user_text(value: str | None) -> str:
    if not value:
        return ""

    text = str(value)
    text = _TATWEEL_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = _REPEAT_PUNCT_RE.sub(r"\1", text)
    text = _REPEAT_CHAR_RE.sub(r"\1", text)

    text = _BAD_DATA_RE.sub("بيانات غير صحيحة", text)
    return text.strip()
