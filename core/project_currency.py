from __future__ import annotations

from typing import Any

BASE_CURRENCY_CODE = "EGP"
_CURRENCY_ALIASES = {
    "EGY": BASE_CURRENCY_CODE,
}
_CURRENCY_SUFFIXES = {
    BASE_CURRENCY_CODE: "?.?",
    "USD": "USD",
    "SAR": "SAR",
    "AED": "AED",
}


def normalize_currency_code(value: Any, default: str = BASE_CURRENCY_CODE) -> str:
    raw_value = getattr(value, "value", value)
    code = str(raw_value or "").strip().upper()
    if not code:
        return default
    return _CURRENCY_ALIASES.get(code, code)


def normalize_exchange_rate(value: Any, currency_code: Any = BASE_CURRENCY_CODE) -> float:
    code = normalize_currency_code(currency_code)
    try:
        rate = float(value)
    except (TypeError, ValueError):
        rate = 1.0
    if rate <= 0:
        rate = 1.0
    if code == BASE_CURRENCY_CODE:
        return 1.0
    return rate


def currency_suffix(currency_code: Any) -> str:
    code = normalize_currency_code(currency_code)
    return _CURRENCY_SUFFIXES.get(code, code)


def amount_to_egp(amount: Any, currency_code: Any, exchange_rate: Any) -> float:
    code = normalize_currency_code(currency_code)
    try:
        numeric_amount = float(amount or 0.0)
    except (TypeError, ValueError):
        return 0.0
    rate = normalize_exchange_rate(exchange_rate, code)
    if code == BASE_CURRENCY_CODE:
        return numeric_amount
    return numeric_amount * rate


def amount_from_egp(amount: Any, currency_code: Any, exchange_rate: Any) -> float:
    code = normalize_currency_code(currency_code)
    try:
        numeric_amount = float(amount or 0.0)
    except (TypeError, ValueError):
        return 0.0
    rate = normalize_exchange_rate(exchange_rate, code)
    if code == BASE_CURRENCY_CODE:
        return numeric_amount
    return numeric_amount / rate


def amount_between_currencies(
    amount: Any,
    from_currency_code: Any,
    from_exchange_rate: Any,
    to_currency_code: Any,
    to_exchange_rate: Any,
) -> float:
    egp_amount = amount_to_egp(amount, from_currency_code, from_exchange_rate)
    return amount_from_egp(egp_amount, to_currency_code, to_exchange_rate)


def project_currency_code(project: Any) -> str:
    if isinstance(project, dict):
        return normalize_currency_code(project.get("currency"))
    return normalize_currency_code(getattr(project, "currency", None))


def project_exchange_rate(project: Any) -> float:
    if isinstance(project, dict):
        return normalize_exchange_rate(
            project.get("exchange_rate_snapshot"),
            project.get("currency"),
        )
    return normalize_exchange_rate(
        getattr(project, "exchange_rate_snapshot", 1.0),
        getattr(project, "currency", None),
    )


def project_currency_suffix(project: Any) -> str:
    return currency_suffix(project_currency_code(project))


def project_amount_from_egp(amount: Any, project: Any) -> float:
    return amount_from_egp(amount, project_currency_code(project), project_exchange_rate(project))


def project_amount_to_egp(amount: Any, project: Any) -> float:
    return amount_to_egp(amount, project_currency_code(project), project_exchange_rate(project))
