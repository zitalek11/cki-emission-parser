from tests.helpers import add_document, build_job, field_spec, mini_set

from cki_emission_parser.extraction.llm import ScriptedLlmProvider
from cki_emission_parser.extraction.pipeline import extract_job
from cki_emission_parser.extraction.verify import apply_verification
from cki_emission_parser.models.types import Evidence, FieldResult, SourceFragment


def test_verify_rejects_quote_missing_from_fragment() -> None:
    fragment = SourceFragment(
        source_id="src_001",
        document_id="doc_001",
        document_name="decision.pdf",
        document_type="issuance_decision",
        page=1,
        text="Полное фирменное наименование эмитента: ПАО «Север».",
    )
    spec = field_spec()
    result = FieldResult(
        field=spec.id,
        raw_value="ПАО «Восток»",
        status="confirmed",
        evidence=[Evidence(source_id="src_001", quote="полное фирменное наименование эмитента: ПАО «Восток»")],
        canonical_source="src_001",
        extraction_method="direct",
        quality_score=0.7,
        review_decision="accepted",
    )
    checked = apply_verification(spec, result, [fragment])
    assert checked.status == "not_found"
    assert checked.raw_value is None


def test_conflict_keeps_both_quotes() -> None:
    job = build_job("Полное фирменное наименование эмитента: ПАО «Север».")
    add_document(
        job,
        "Полное фирменное наименование эмитента: ПАО «Восток».",
        document_id="doc_002",
        filename="program.pdf",
        document_type="bond_program",
        source_id="src_002",
    )
    provider = ScriptedLlmProvider(
        {
            "issuer.name_full": [
                {
                    "value": "ПАО «Север»",
                    "evidence_source_id": "src_001",
                    "quote": "Полное фирменное наименование эмитента: ПАО «Север».",
                },
                {
                    "value": "ПАО «Восток»",
                    "evidence_source_id": "src_002",
                    "quote": "Полное фирменное наименование эмитента: ПАО «Восток».",
                },
            ]
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(field_spec()),
        instrument_class="bond_exchange",
    )
    field = report.fields[0]
    assert field.status == "conflict"
    assert field.review_decision == "review_required"
    assert len(field.evidence) == 2
    quotes = {item.quote for item in field.evidence}
    assert any("Север" in quote for quote in quotes)
    assert any("Восток" in quote for quote in quotes)
    assert provider.calls == ["issuer.name_full", "issuer.name_full"]


def test_agreeing_documents_keep_one_value_and_both_sources() -> None:
    job = build_job("Полное фирменное наименование эмитента: ПАО «Север».")
    add_document(
        job,
        "Полное фирменное наименование эмитента: ПАО «Север».",
        document_id="doc_002",
        filename="program.pdf",
        document_type="bond_program",
        source_id="src_002",
    )
    provider = ScriptedLlmProvider(
        {
            "issuer.name_full": [
                {
                    "value": "ПАО «Север»",
                    "evidence_source_id": "src_001",
                    "quote": "Полное фирменное наименование эмитента: ПАО «Север».",
                },
                {
                    "value": "ПАО «Север»",
                    "evidence_source_id": "src_002",
                    "quote": "Полное фирменное наименование эмитента: ПАО «Север».",
                },
            ]
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
    assert field.raw_value == "ПАО «Север»"
    assert len(field.evidence) == 2
    assert field.canonical_source == "src_001"
    assert "src_002" in field.supporting_sources


def test_unknown_parameter_is_unmapped_not_stuffed() -> None:
    job = build_job(
        "Полное фирменное наименование эмитента: ПАО «Север».\n"
        "Барьер досрочного погашения: 80% от номинала."
    )
    provider = ScriptedLlmProvider(
        {
            "issuer.name_full": {
                "value": "ПАО «Север»",
                "evidence_source_id": "src_001",
                "quote": "Полное фирменное наименование эмитента: ПАО «Север».",
            }
        }
    )
    report = extract_job(
        job,
        provider=provider,
        extract_set=mini_set(field_spec()),
        instrument_class="bond_exchange",
    )
    labels = [fact.label.casefold() for fact in report.unmapped_facts]
    assert any("барьер" in label for label in labels)
    assert all("фирменное наименование" not in label for label in labels)
    assert report.fields[0].status == "confirmed"
    assert report.fields[0].raw_value == "ПАО «Север»"
