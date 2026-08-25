from tests.helpers import build_job, field_spec, mini_set

from cki_emission_parser.extraction.llm import ScriptedLlmProvider
from cki_emission_parser.extraction.pipeline import extract_job
from cki_emission_parser.models.types import Evidence, FieldResult
from cki_emission_parser.validate import apply_validation


def _confirmed(spec_id: str, value: object, quote: str) -> FieldResult:
    return FieldResult(
        field=spec_id,
        raw_value=value,
        normalized_value=value,
        status="confirmed",
        evidence=[Evidence(source_id="src_001", quote=quote, page=1)],
        canonical_source="src_001",
        extraction_method="direct",
        quality_score=0.7,
        review_decision="accepted",
    )


def test_inn_from_url_is_rejected() -> None:
    job = build_job("Страница раскрытия: https://e-disclosure.ru/portal/files.aspx?inn=7707083893")
    spec = field_spec(
        id="issuer.inn",
        type="string",
        nrd_path="issuer.inn",
        synonyms=["ИНН", "страница раскрытия"],
    )
    provider = ScriptedLlmProvider(
        {
            "issuer.inn": {
                "value": "7707083893",
                "evidence_source_id": "src_001",
                "quote": "https://e-disclosure.ru/portal/files.aspx?inn=7707083893",
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(spec),
        instrument_class="bond_exchange",
    )
    assert report.fields[0].status == "not_found"
    assert report.fields[0].raw_value is None


def test_labeled_inn_is_kept() -> None:
    job = build_job("ИНН эмитента: 7707083893")
    spec = field_spec(id="issuer.inn", type="string", nrd_path="issuer.inn", synonyms=["ИНН"])
    provider = ScriptedLlmProvider(
        {
            "issuer.inn": {
                "value": "7707083893",
                "evidence_source_id": "src_001",
                "quote": "ИНН эмитента: 7707083893",
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
    assert field.normalized_value == "7707083893"


def test_short_name_cannot_be_taken_from_full_name_quote() -> None:
    quote = (
        "Полное фирменное наименование эмитента: "
        "Публичное акционерное общество «Северная магистраль»."
    )
    spec = field_spec(
        id="issuer.name_short",
        type="string",
        nrd_path="issuer.name_short",
        synonyms=["сокращённое фирменное наименование", "полное фирменное наименование"],
    )
    result = apply_validation(
        spec,
        _confirmed("issuer.name_short", "ПАО «Северная магистраль»", quote),
        build_job(quote).documents[0].fragments,
    )
    assert result.status == "not_found"


def test_explicit_short_name_is_kept() -> None:
    quote = "Сокращённое фирменное наименование эмитента: ПАО «Северная магистраль»."
    spec = field_spec(
        id="issuer.name_short",
        type="string",
        nrd_path="issuer.name_short",
        synonyms=["сокращённое фирменное наименование"],
    )
    result = apply_validation(
        spec,
        _confirmed("issuer.name_short", "ПАО «Северная магистраль»", quote),
        build_job(quote).documents[0].fragments,
    )
    assert result.status == "confirmed"


def test_cfi_is_not_inferred_from_bond_wording() -> None:
    quote = "Биржевые облигации процентные неконвертируемые бездокументарные."
    spec = field_spec(id="cfi", type="string", nrd_path="cfi", synonyms=["CFI", "биржевые облигации"])
    result = apply_validation(
        spec,
        _confirmed("cfi", "DBFUFB", quote),
        build_job(quote).documents[0].fragments,
    )
    assert result.status == "not_found"


def test_planned_size_rejects_actual_placement_quote() -> None:
    quote = "Фактически размещено 10 000 акций дополнительного выпуска."
    spec = field_spec(
        id="share.issue_size_planned",
        type="integer",
        nrd_path="share.issue_size_planned",
        applies_to=["share_common"],
        synonyms=["фактически размещено", "количество размещаемых"],
    )
    result = apply_validation(
        spec,
        _confirmed("share.issue_size_planned", 10000, quote),
        build_job(quote).documents[0].fragments,
    )
    assert result.status == "not_found"


def test_issued_size_rejects_planned_quote() -> None:
    quote = "Количество размещаемых акций дополнительного выпуска: 10 000."
    spec = field_spec(
        id="share.issued_size",
        type="integer",
        nrd_path="share.issued_size",
        applies_to=["share_common"],
        synonyms=["количество размещаемых", "фактически размещенных"],
    )
    result = apply_validation(
        spec,
        _confirmed("share.issued_size", 10000, quote),
        build_job(quote).documents[0].fragments,
    )
    assert result.status == "not_found"


def test_ogrn_of_counterparty_is_rejected() -> None:
    quote = "ОГРН покупателя: 1027700132195."
    spec = field_spec(id="issuer.ogrn", type="string", nrd_path="issuer.ogrn", synonyms=["ОГРН"])
    result = apply_validation(
        spec,
        _confirmed("issuer.ogrn", "1027700132195", quote),
        build_job(quote).documents[0].fragments,
    )
    assert result.status == "not_found"
