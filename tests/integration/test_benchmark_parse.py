from pathlib import Path

import pytest

from cki_emission_parser.ingestion import ingest_pack

BENCHMARK = Path(__file__).resolve().parents[2].parent / "_benchmark_artifacts" / "Артефакты для справочника выпусков"


@pytest.mark.skipif(not BENCHMARK.exists(), reason="Эталонный архив не распакован")
def test_digital_bond_decision_parses() -> None:
    pdf = next(
        BENCHMARK.joinpath("Биржевые облигации", "Пример 1").glob("Решение*.pdf")
    )
    job = ingest_pack(pdf)
    doc = job.documents[0]
    assert doc.page_count >= 1
    assert doc.fragments
    blob = " ".join(fragment.text for fragment in doc.fragments)
    assert "облигац" in blob.lower() or "решение" in blob.lower()
