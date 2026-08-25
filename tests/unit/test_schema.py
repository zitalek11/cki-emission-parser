from cki_emission_parser.schema import load_extract_set, load_nrd_catalog


def test_nrd_catalog_is_large_and_not_the_prompt_set() -> None:
    catalog = load_nrd_catalog()
    extract = load_extract_set()
    assert len(catalog.fields) > 500
    assert 10 <= len(extract.fields) <= 80
    assert len(extract.fields) < len(catalog.fields) / 5


def test_extract_set_does_not_allow_cfi_derivation() -> None:
    extract = load_extract_set()
    cfi = next(field for field in extract.fields if field.id == "cfi")
    assert cfi.required_evidence is True
    assert cfi.allow_derivation is False


def test_short_name_cannot_be_derived() -> None:
    extract = load_extract_set()
    short = next(field for field in extract.fields if field.id == "issuer.name_short")
    assert short.allow_derivation is False
    assert short.required_evidence is True


def test_unknown_instrument_still_has_fields() -> None:
    extract = load_extract_set()
    assert extract.for_instrument("unknown")
    assert len(extract.for_instrument("unknown")) == len(extract.fields)


def test_currency_derivation_is_an_explicit_code_rule() -> None:
    extract = load_extract_set()
    currency = next(field for field in extract.fields if field.id == "bond.currency.code")
    assert currency.allow_derivation is True
    assert currency.derivation_rule == "currency_from_text"
    cfi = next(field for field in extract.fields if field.id == "cfi")
    assert cfi.allow_derivation is False
    assert cfi.derivation_rule is None
