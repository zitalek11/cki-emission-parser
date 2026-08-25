from tests.helpers import build_job, field_spec

from cki_emission_parser.extraction.retrieve import retrieve_candidates
from cki_emission_parser.models.types import ParsedDocument, SourceFragment
from cki_emission_parser.schema import load_extract_set


def test_retrieves_by_synonym() -> None:
    job = build_job("Полное фирменное наименование эмитента: ПАО «Пример».")
    hits = retrieve_candidates(job, field_spec())
    assert hits
    assert hits[0][0].source_id == "src_001"


def test_retrieves_from_extract_set_without_issuer_name() -> None:
    job = build_job("Иные идентификационные признаки выпуска: биржевые облигации процентные.")
    spec = next(field for field in load_extract_set().fields if field.id == "name_full")
    assert retrieve_candidates(job, spec)


def test_no_hit_without_field_language() -> None:
    job = build_job("Повестка заседания: утвердить регламент.")
    assert retrieve_candidates(job, field_spec()) == []


def test_preferred_document_type_boosts_score() -> None:
    job = build_job(
        "полное фирменное наименование эмитента: ПАО Пример",
        document_type="prospectus",
    )
    other = SourceFragment(
        source_id="src_002",
        document_id="doc_002",
        document_name="decision.pdf",
        document_type="issuance_decision",
        page=1,
        order=1,
        text="полное фирменное наименование эмитента: ПАО Пример",
    )
    job.documents.append(
        ParsedDocument(
            document_id="doc_002",
            path="decision.pdf",
            filename="decision.pdf",
            media_type="pdf",
            document_type="issuance_decision",
            page_count=1,
            fragments=[other],
        )
    )
    hits = retrieve_candidates(job, field_spec())
    assert hits[0][0].source_id == "src_002"


def test_new_issuer_still_retrieves() -> None:
    spec = field_spec()
    gazprom = build_job("Полное фирменное наименование эмитента: ПАО «Газпром»")
    rzd = build_job("Полное фирменное наименование эмитента: ОАО «РЖД»")
    assert retrieve_candidates(gazprom, spec)
    assert retrieve_candidates(rzd, spec)
