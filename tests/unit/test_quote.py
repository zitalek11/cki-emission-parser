from cki_emission_parser.extraction.quote import (
    normalize_match_text,
    quote_in_text,
    value_supported_by_quote,
)


def test_normalize_collapses_yo_and_whitespace() -> None:
    assert normalize_match_text("  Ёлка\nзелёная  ") == "елка зеленая"


def test_quote_must_be_literal_fragment() -> None:
    text = "Номинальная стоимость каждой облигации составляет 1 000 рублей."
    assert quote_in_text("1 000 рублей", text)
    assert not quote_in_text("номинал равен тысяче", text)


def test_invented_short_quote_is_rejected() -> None:
    assert not quote_in_text("да", "да, облигации размещаются")


def test_numeric_value_matches_spaced_thousands() -> None:
    quote = "номинальная стоимость каждой ценной бумаги: 1 000 российских рублей"
    assert value_supported_by_quote(1000, quote, quote)
    assert value_supported_by_quote(1000.0, quote, quote)


def test_boolean_false_requires_negation_in_quote() -> None:
    positive = "облигации предназначены для квалифицированных инвесторов"
    negative = "не являются ценными бумагами, предназначенными для квалифицированных инвесторов"
    assert value_supported_by_quote(True, positive, positive)
    assert not value_supported_by_quote(False, positive, positive)
    assert value_supported_by_quote(False, negative, negative)
    assert not value_supported_by_quote(True, negative, negative)
