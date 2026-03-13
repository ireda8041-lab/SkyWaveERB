from __future__ import annotations

import re
from collections.abc import Iterable

from core.text_utils import normalize_user_text

_TREASURY_TYPE_PREFIX = "نوع الخزنة:"
_COMPACT_LOOKUP_RE = re.compile(r"[\s\-_:/\\|]+")
_CASH_ACCOUNT_TYPE_ALIASES = frozenset({"أصول نقدية", "cash", "CASH"})


def _compact_lookup_text(*parts: object) -> str:
    text = normalize_user_text(" ".join(str(part or "") for part in parts)).casefold()
    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return _COMPACT_LOOKUP_RE.sub("", text)


def get_cashbox_treasury_type(account: schemas.Account | object) -> str:
    raw_description = str(getattr(account, "description", "") or "")
    for line in raw_description.splitlines():
        stripped = line.strip()
        if stripped.startswith(_TREASURY_TYPE_PREFIX):
            return stripped.split(":", 1)[1].strip()

    name = str(getattr(account, "name", "") or "")
    code = str(getattr(account, "code", "") or "").strip()
    if bool(getattr(account, "is_group", False)) or code in {
        "111000",
        "111100",
        "111200",
        "111300",
    }:
        return ""
    lookup = _compact_lookup_text(name, raw_description)

    if any(token in lookup for token in ("vodafone", "فودافون", "vf", "محفظه")):
        return "محفظة إلكترونية"
    if "instapay" in lookup or "انستاباي" in lookup or code == "111003":
        return "إنستا باي"
    if any(token in lookup for token in ("بنك", "bank", "iban", "swiftcode")):
        if any(token in lookup for token in ("دولي", "خارجمصر", "international", "iban")):
            return "تحويل بنكي دولي"
        return "تحويل بنكي داخل مصر"
    if any(token in lookup for token in ("نقدي", "كاش", "cash", "خزينه", "خزنه", "صندوق", "عهده")):
        return "خزنة نقدية"
    if code in {"111006", "111101", "111102"}:
        return "خزنة نقدية"
    return ""


def infer_payment_method_from_account(account: schemas.Account | object | None) -> str:
    if account is None:
        return "Other"

    name = str(getattr(account, "name", "") or "")
    code = str(getattr(account, "code", "") or "").strip()
    if bool(getattr(account, "is_group", False)) or code in {
        "111000",
        "111100",
        "111200",
        "111300",
    }:
        return "Other"
    treasury_type = get_cashbox_treasury_type(account)
    lookup = _compact_lookup_text(name, treasury_type, getattr(account, "description", ""))

    if any(token in lookup for token in ("vodafone", "فودافون", "vf")):
        return "VF Cash"
    if "instapay" in lookup or "انستاباي" in lookup or treasury_type == "إنستا باي":
        return "InstaPay"
    if treasury_type == "تحويل بنكي داخل مصر":
        return "Bank Misr Local"
    if treasury_type == "تحويل بنكي دولي":
        return "Bank Misr Intl"
    if any(token in lookup for token in ("بنك", "bank", "iban", "swiftcode")):
        return "Bank Transfer"
    if treasury_type == "خزنة نقدية" or any(
        token in lookup for token in ("نقدي", "كاش", "cash", "خزينه", "خزنه", "صندوق", "عهده")
    ):
        return "Cash"
    if "شيك" in lookup or "check" in lookup:
        return "Check"

    if code in {"111001", "111002"} or code.startswith("1113") or code.startswith("1103"):
        return "VF Cash"
    if code == "111003" or code.startswith("1104"):
        return "InstaPay"
    if code == "111004":
        return "Bank Misr Local"
    if code == "111005":
        return "Bank Misr Intl"
    if code.startswith("1112") or code.startswith("1102"):
        return "Bank Transfer"
    if code in {"111006", "111101", "111102"} or code.startswith("1101"):
        return "Cash"
    return "Other"


def is_operational_cashbox(account: schemas.Account | object) -> bool:
    code = str(getattr(account, "code", "") or "").strip()
    if not code:
        return False

    account_type = getattr(account, "type", None)
    type_value = str(getattr(account_type, "value", account_type) or "").strip()
    is_group = bool(getattr(account, "is_group", False))

    if is_group:
        return False

    return type_value in _CASH_ACCOUNT_TYPE_ALIASES or code.startswith("111")


def filter_operational_cashboxes(
    accounts: Iterable[schemas.Account] | None,
) -> list[schemas.Account]:
    if not accounts:
        return []
    return [account for account in accounts if is_operational_cashbox(account)]
