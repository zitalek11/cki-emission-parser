from tests.helpers import build_job, field_spec, mini_set

from cki_emission_parser.cli import _prefer_model
from cki_emission_parser.extraction.llm import (
    NullLlmProvider,
    ScriptedLlmProvider,
    _want_json_object,
    normalize_base_url,
    resolve_model,
)
from cki_emission_parser.extraction.pipeline import extract_job
from cki_emission_parser.schema import load_extract_set

ISSUER_TEXT = (
    "Полное фирменное наименование эмитента: "
    "Публичное акционерное общество «Северная магистраль»."
)


def test_null_llm_never_confirms() -> None:
    job = build_job(ISSUER_TEXT)
    report = extract_job(
        job,
        provider=NullLlmProvider(),
        extract_set=mini_set(field_spec()),
        instrument_class="bond_exchange",
    )
    assert report.llm_used is False
    assert report.fields[0].status == "not_found"
    assert report.fields[0].raw_value is None


def test_no_candidates_does_not_call_llm() -> None:
    job = build_job("Повестка: утвердить регламент работы комиссии.")
    provider = ScriptedLlmProvider(
        {
            "issuer.name_full": {
                "value": "выдумка",
                "evidence_source_id": "src_001",
                "quote": "Повестка: утвердить",
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(field_spec()),
        instrument_class="bond_exchange",
    )
    assert provider.calls == []
    assert report.fields[0].status == "not_found"
    assert report.fields[0].raw_value is None


def test_invented_quote_is_not_confirmed() -> None:
    job = build_job(ISSUER_TEXT)
    provider = ScriptedLlmProvider(
        {
            "issuer.name_full": {
                "value": "ПАО «МТС»",
                "evidence_source_id": "src_001",
                "quote": "полное фирменное наименование эмитента: ПАО «МТС»",
                "status": "confirmed",
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(field_spec()),
        instrument_class="bond_exchange",
    )
    assert report.fields[0].status == "not_found"
    assert report.fields[0].raw_value is None


def test_literal_quote_is_confirmed_by_code_not_llm() -> None:
    job = build_job(ISSUER_TEXT)
    quote = (
        "Полное фирменное наименование эмитента: "
        "Публичное акционерное общество «Северная магистраль»."
    )
    provider = ScriptedLlmProvider(
        {
            "issuer.name_full": {
                "value": "Публичное акционерное общество «Северная магистраль»",
                "evidence_source_id": "src_001",
                "quote": quote,
                "status": "guess",
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(field_spec()),
        instrument_class="bond_exchange",
    )
    field = report.fields[0]
    assert field.status == "confirmed"
    assert field.raw_value == "Публичное акционерное общество «Северная магистраль»"
    assert field.evidence[0].source_id == "src_001"
    assert field.review_decision == "accepted"


def test_silence_is_not_false_for_qualified_investors() -> None:
    job = build_job(ISSUER_TEXT)
    qualified = next(
        field for field in load_extract_set().fields if field.id == "for_qualified_investors"
    )
    provider = ScriptedLlmProvider(
        {
            "for_qualified_investors": {
                "value": False,
                "evidence_source_id": "src_001",
                "quote": "эмитент не указывает ограничений",
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(qualified),
        instrument_class="bond_exchange",
    )
    assert provider.calls == []
    field = report.fields[0]
    assert field.status == "not_found"
    assert field.raw_value is None


def test_wrong_source_id_is_rejected() -> None:
    job = build_job(ISSUER_TEXT)
    provider = ScriptedLlmProvider(
        {
            "issuer.name_full": {
                "value": "Публичное акционерное общество «Северная магистраль»",
                "evidence_source_id": "src_999",
                "quote": ISSUER_TEXT,
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(field_spec()),
        instrument_class="bond_exchange",
    )
    assert report.fields[0].status == "not_found"


def test_moex_skips_json_object_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CKI_LLM_JSON_OBJECT", raising=False)
    assert _want_json_object("https://api-new.ai.moex.com/v1") is False
    assert _want_json_object("https://openrouter.ai/api/v1") is True


def test_prefer_strong_model_id() -> None:
    assert _prefer_model(["fast", "strong", "medium"]) == "strong"


def test_normalize_moex_base_url() -> None:
    assert normalize_base_url("https://api-new.ai.moex.com") == "https://api-new.ai.moex.com/v1"
    assert (
        normalize_base_url("https://api-new.ai.moex.com/v1/chat/completions")
        == "https://api-new.ai.moex.com/v1"
    )


def test_moex_rejects_openrouter_model_id() -> None:
    assert resolve_model("https://api-new.ai.moex.com/v1", "openai/gpt-4o-mini") == "strong"
    assert resolve_model("https://api-new.ai.moex.com/v1", None) == "strong"
    assert resolve_model("https://api-new.ai.moex.com/v1", "fast") == "fast"
