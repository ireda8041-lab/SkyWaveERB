import pytest

from core.sqlite_identifiers import (
    quote_expression,
    quote_expression_list,
    quote_identifier,
    quote_identifier_list,
)


def test_quote_identifier_quotes_valid_identifier():
    assert quote_identifier("clients") == '"clients"'


def test_quote_identifier_rejects_invalid_identifier():
    with pytest.raises(ValueError):
        quote_identifier("clients; DROP TABLE clients")


def test_quote_identifier_list_rejects_unsupported_identifier():
    with pytest.raises(ValueError):
        quote_identifier_list(["name", "status"], allowed={"name"})


def test_quote_expression_allows_only_expected_wrappers():
    assert quote_expression("LOWER(name)", allowed_identifiers={"name"}) == 'LOWER("name")'

    with pytest.raises(ValueError):
        quote_expression("MAX(name)", allowed_identifiers={"name"})


def test_quote_expression_list_quotes_each_expression():
    expressions = quote_expression_list(
        ("LOWER(name)", "client_id"), allowed_identifiers={"name", "client_id"}
    )

    assert expressions == ['LOWER("name")', '"client_id"']
