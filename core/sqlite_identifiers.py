"""Helpers for safely embedding SQLite identifiers in static SQL templates."""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LOWER_EXPR_RE = re.compile(r"^LOWER\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)$", re.IGNORECASE)


def _normalize_allowed(allowed: Collection[str] | None) -> set[str] | None:
    if allowed is None:
        return None
    return {str(item).strip() for item in allowed}


def quote_identifier(identifier: str, *, allowed: Collection[str] | None = None) -> str:
    """Quote a validated SQLite identifier."""

    normalized = str(identifier or "").strip()
    allowed_set = _normalize_allowed(allowed)

    if allowed_set is not None and normalized not in allowed_set:
        raise ValueError(f"Unsupported SQLite identifier: {normalized}")
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"Invalid SQLite identifier: {normalized}")

    return f'"{normalized}"'


def quote_identifier_list(
    identifiers: Iterable[str], *, allowed: Collection[str] | None = None
) -> list[str]:
    """Quote multiple validated SQLite identifiers."""

    allowed_set = _normalize_allowed(allowed)
    return [quote_identifier(identifier, allowed=allowed_set) for identifier in identifiers]


def quote_expression(expression: str, *, allowed_identifiers: Collection[str] | None = None) -> str:
    """Quote a restricted SQL expression built from trusted identifiers only."""

    normalized = str(expression or "").strip()
    match = _LOWER_EXPR_RE.fullmatch(normalized)
    if match:
        identifier = quote_identifier(match.group(1), allowed=allowed_identifiers)
        return f"LOWER({identifier})"

    return quote_identifier(normalized, allowed=allowed_identifiers)


def quote_expression_list(
    expressions: Iterable[str], *, allowed_identifiers: Collection[str] | None = None
) -> list[str]:
    """Quote multiple restricted SQL expressions."""

    allowed_set = _normalize_allowed(allowed_identifiers)
    return [
        quote_expression(expression, allowed_identifiers=allowed_set) for expression in expressions
    ]
