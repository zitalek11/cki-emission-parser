from tests.helpers import build_job, field_spec, mini_set

from cki_emission_parser.extraction.llm import NullLlmProvider, ScriptedLlmProvider
from cki_emission_parser.extraction.pipeline import extract_job
from cki_emission_parser.normalize.dates import parse_date_value
from cki_emission_parser.normalize.values import CannotNormalize, normalize_value


def test_integer_parses_grouped_thousands() -> None:
    spec = field_spec(id="bond.issue_size_planned", type="integer")
    assert normalize_value(spec, "10 000", "количество размещаемых облигаций: 10 000") == 10000


def test_integer_rejects_excel_calendar_date() -> None:
    spec = field_spec(id="bond.coupons_number", type="integer")
    try:
        normalize_value(spec, "2024-01-15", "число купонов")
    except CannotNormalize:
        return
    raise AssertionError("календарная дата не должна становиться целым")


def test_exact_date_becomes_iso() -> None:
    spec = field_spec(id="state_reg_date", type="date")
    value = parse_date_value("15 марта 2024", "дата государственной регистрации: 15 марта 2024 г.")
    assert value.date_kind == "exact"
    assert value.normalized == "2024-03-15"


def test_date_rule_is_not_flattened_to_calendar() -> None:
    quote = "Облигации погашаются в 3600-й день с даты начала размещения."
    value = parse_date_value("2034-05-20", quote)
    assert value.date_kind == "rule"
    assert value.normalized is None
    assert "3600-й день" in value.raw_text


def test_currency_derived_without_llm() -> None:
    job = build_job("Номинальная стоимость каждой облигации составляет 1 000 российских рублей.")
    spec = field_spec(
        id="bond.currency.code",
        type="currency",
        nrd_path="bond.currency.code",
        synonyms=["российских рублей", "валюта номинала"],
        allow_derivation=True,
        derivation_rule="currency_from_text",
    )
    report = extract_job(
        job,
        provider=NullLlmProvider(),
        extract_set=mini_set(spec),
        instrument_class="bond_exchange",
    )
    field = report.fields[0]
    assert field.status == "derived"
    assert field.normalized_value == "RUB"
    assert field.derivation_rule == "currency_from_text"
    assert field.extraction_method == "derived"
    assert field.evidence[0].quote


def test_extracted_ruble_phrase_normalizes_to_rub() -> None:
    job = build_job("Валюта номинала: российские рубли.")
    spec = field_spec(
        id="bond.currency.code",
        type="currency",
        nrd_path="bond.currency.code",
        synonyms=["валюта номинала", "российские рубли"],
        allow_derivation=True,
        derivation_rule="currency_from_text",
    )
    provider = ScriptedLlmProvider(
        {
            "bond.currency.code": {
                "value": "российские рубли",
                "evidence_source_id": "src_001",
                "quote": "Валюта номинала: российские рубли.",
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(spec),
        instrument_class="bond_exchange",
    )
    field = report.fields[0]
    assert field.status == "confirmed"
    assert field.normalized_value == "RUB"


def test_pipeline_keeps_date_rule() -> None:
    quote = "Срок погашения: 3600-й день с даты начала размещения."
    job = build_job(quote)
    spec = field_spec(
        id="bond.expiry_date_plan",
        type="date",
        nrd_path="bond.expiry_date_plan",
        synonyms=["срок погашения", "погашаются"],
        date_kinds=["exact", "rule", "relative", "range"],
    )
    provider = ScriptedLlmProvider(
        {
            "bond.expiry_date_plan": {
                "value": "3600-й день с даты начала размещения",
                "evidence_source_id": "src_001",
                "quote": quote,
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(spec),
        instrument_class="bond_exchange",
    )
    field = report.fields[0]
    assert field.status == "confirmed"
    assert field.normalized_value["date_kind"] == "rule"
    assert field.normalized_value["normalized"] is None
