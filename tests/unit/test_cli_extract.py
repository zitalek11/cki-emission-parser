import json
from pathlib import Path

from tests.helpers import build_job, field_spec, mini_set

from cki_emission_parser.cli import main
from cki_emission_parser.extraction.llm import NullLlmProvider
from cki_emission_parser.extraction.pipeline import extract_job
from cki_emission_parser.output.json_dump import report_to_dict


def test_extract_report_json_has_fields_not_fragments() -> None:
    job = build_job("Полное фирменное наименование эмитента: ПАО «Пример»")
    report = extract_job(
        job,
        provider=NullLlmProvider(),
        extract_set=mini_set(field_spec()),
        instrument_class="bond_exchange",
    )
    payload = report_to_dict(report)
    assert "fields" in payload
    assert "status_counts" in payload
    assert "review_queue" in payload
    assert "fragments" not in payload
    assert "retrieval" not in payload


def test_dry_retrieve_cli(digital_pdf: Path, capsys) -> None:
    code = main([str(digital_pdf), "--dry-retrieve", "--instrument", "bond_exchange"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["instrument_class"] == "bond_exchange"
    assert "issuer.name_full" in payload["hit_fields"]
    assert payload["retrieval"]["issuer.name_full"]
    assert "fragments" not in payload
