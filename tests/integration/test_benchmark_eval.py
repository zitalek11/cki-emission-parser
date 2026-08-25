from pathlib import Path

import pytest

from cki_emission_parser.eval.score import load_gold, score_report
from cki_emission_parser.extraction.instrument import guess_instrument_class
from cki_emission_parser.extraction.llm import NullLlmProvider
from cki_emission_parser.extraction.pipeline import extract_job
from cki_emission_parser.extraction.retrieve import retrieve_job
from cki_emission_parser.ingestion import ingest_pack

BENCHMARK = (
    Path(__file__).resolve().parents[2].parent
    / "_benchmark_artifacts"
    / "Артефакты для справочника выпусков"
)
GOLD = Path(__file__).resolve().parents[2] / "config" / "eval" / "gold.yaml"

pytestmark = pytest.mark.skipif(not BENCHMARK.exists(), reason="Эталонный архив не распакован")


def _pack(*parts: str) -> Path:
    return BENCHMARK.joinpath(*parts)


def _score(pack: Path):
    job = ingest_pack(pack)
    job.instrument_class = guess_instrument_class(job)
    report = extract_job(job, provider=NullLlmProvider(), instrument_class=job.instrument_class)
    gold = load_gold(GOLD)
    return job, report, score_report(report, gold, pack_path=str(pack))


def test_digital_exchange_bond_is_not_structured_and_derives_rub() -> None:
    pack = _pack("Биржевые облигации", "Пример 1")
    job, report, score = _score(pack)
    assert job.instrument_class == "bond_exchange"
    assert score["instrument_ok"] is True
    assert score["unsupported_value_rate"] == 0.0
    currency = next(field for field in report.fields if field.field == "bond.currency.code")
    assert currency.status == "derived"
    assert currency.normalized_value == "RUB"
    assert score["hits"] >= 1
    cfi = next(field for field in report.fields if field.field == "cfi")
    assert cfi.status == "not_found"


def test_second_exchange_pack_does_not_take_nsd_inn() -> None:
    pack = _pack("Биржевые облигации", "Пример 2")
    _job, report, score = _score(pack)
    assert score["instrument_ok"] is True
    assert score["unsupported_value_rate"] == 0.0
    assert score["reproduced_known_bad"] == 0
    inn = next(field for field in report.fields if field.field == "issuer.inn")
    assert inn.status == "not_found"
    assert inn.raw_value != "7702165310"


def test_incomplete_pref_pack_still_retrieves() -> None:
    pack = _pack("Акции привилегированные", "Пример 2")
    job = ingest_pack(pack)
    assert len(job.documents) == 1
    assert job.documents[0].page_count == 3
    resolved, retrieval = retrieve_job(job)
    assert resolved == "share_pref"
    assert retrieval["issuer.name_full"]
    assert retrieval["share.face_value"]
    _job, _report, score = _score(pack)
    assert score["instrument_ok"] is True
    assert score["unsupported_value_rate"] == 0.0


def test_structured_docx_classified_from_title() -> None:
    pack = _pack("Стрктурные облигации", "Пример 1")
    job, report, score = _score(pack)
    assert job.instrument_class == "bond_structured"
    assert score["instrument_ok"] is True
    assert score["unsupported_value_rate"] == 0.0
    currency = next(field for field in report.fields if field.field == "bond.currency.code")
    assert currency.normalized_value == "RUB"


def test_scan_pack_ocr_gate_does_not_invent_values() -> None:
    pack = _pack("Акция обыкновенные", "Пример 1")
    job, report, score = _score(pack)
    assert any(document.pages_needing_ocr for document in job.documents)
    assert all(len(document.fragments) == 0 for document in job.documents)
    assert job.instrument_class == "share_common"
    filled = [field for field in report.fields if field.status not in {"not_found", "not_applicable"}]
    assert filled == []
    assert score["unsupported_value_rate"] == 0.0
    assert score["produced"] == 0
