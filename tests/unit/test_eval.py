from pathlib import Path

from cki_emission_parser.cli import main
from cki_emission_parser.eval.gold import GoldField
from cki_emission_parser.eval.score import load_gold, score_report
from cki_emission_parser.models.types import Evidence, ExtractReport, FieldResult
from cki_emission_parser.output import report_to_dict, write_json

EXAMPLE_GOLD = Path(__file__).resolve().parents[2] / "config" / "eval" / "gold.example.yaml"


def _report(*fields: FieldResult) -> ExtractReport:
    return ExtractReport(
        job_id="eval-job",
        instrument_class="bond_exchange",
        fields=list(fields),
    )


def _field(
    field: str,
    value,
    *,
    status: str = "confirmed",
    quote: str | None = "цитата",
    source_id: str = "src_1",
) -> FieldResult:
    evidence = []
    if quote is not None:
        evidence = [Evidence(source_id=source_id, quote=quote, page=1)]
    return FieldResult(
        field=field,
        raw_value=value,
        normalized_value=value,
        status=status,
        evidence=evidence,
    )


def test_accepted_hit_is_supported() -> None:
    report = _report(
        _field(
            "issuer.name_full",
            "ПАО «Пример»",
            quote="Полное фирменное наименование эмитента: ПАО «Пример»",
        )
    )
    gold = [
        GoldField(
            field="issuer.name_full",
            label="accepted",
            value="ПАО «Пример»",
            quote_contains="ПАО «Пример»",
            slice="known_document",
        )
    ]
    score = score_report(report, gold)
    assert score["unsupported_value_rate"] == 0.0
    assert score["hits"] == 1
    assert score["misses"] == 0


def test_must_be_empty_fill_is_unsupported() -> None:
    report = _report(_field("for_qualified_investors", False, quote="текст без этой оговорки"))
    gold = [
        GoldField(
            field="for_qualified_investors",
            label="must-be-empty",
            slice="silence",
            reason="Молчание не равно нет",
        )
    ]
    score = score_report(report, gold)
    assert score["produced"] == 1
    assert score["unsupported"] == 1
    assert score["unsupported_value_rate"] == 1.0
    assert score["false_fills"] == 1


def test_accepted_not_found_is_miss_not_unsupported() -> None:
    report = _report(
        FieldResult(field="issuer.name_full", status="not_found")
    )
    gold = [GoldField(field="issuer.name_full", label="accepted", value="ПАО «Пример»")]
    score = score_report(report, gold)
    assert score["misses"] == 1
    assert score["produced"] == 0
    assert score["unsupported_value_rate"] == 0.0


def test_known_bad_reproduced_is_unsupported_not_a_win() -> None:
    report = _report(_field("cfi", "ESVUFR", quote="обыкновенные акции"))
    gold = [
        GoldField(
            field="cfi",
            label="known-bad",
            value="ESVUFR",
            slice="derived_without_rule",
            reason="CFI выведен из типа бумаги",
        )
    ]
    score = score_report(report, gold)
    assert score["reproduced_known_bad"] == 1
    assert score["unsupported_value_rate"] == 1.0


def test_known_bad_left_empty_is_ok() -> None:
    report = _report(FieldResult(field="cfi", status="not_found"))
    gold = [GoldField(field="cfi", label="known-bad", value="ESVUFR")]
    score = score_report(report, gold)
    assert score["unsupported_value_rate"] == 0.0
    assert score["produced"] == 0
    assert score["outcomes"]["ok_empty"] == 1


def test_accepted_without_quote_is_unsupported() -> None:
    report = _report(_field("issuer.name_full", "ПАО «Пример»", quote=None))
    gold = [GoldField(field="issuer.name_full", label="accepted", value="ПАО «Пример»")]
    score = score_report(report, gold)
    assert score["unsupported"] == 1
    assert score["details"][0]["outcome"] == "unsupported_quote"


def test_example_gold_loads_and_scores_empty_report() -> None:
    gold = load_gold(EXAMPLE_GOLD)
    labels = {item.field: item.label for item in gold.all_fields()}
    assert labels["for_qualified_investors"] == "must-be-empty"
    assert labels["cfi"] == "known-bad"
    assert labels["issuer.name_full"] == "accepted"
    score = score_report(_report(), gold)
    assert score["labeled"] == 4
    assert score["unsupported_value_rate"] == 0.0
    assert score["misses"] == 1


def test_evaluate_cli_on_json_report(tmp_path: Path, capsys) -> None:
    report = _report(
        _field("cfi", "ESVUFR", quote="обыкновенные акции"),
        FieldResult(field="for_qualified_investors", status="not_found"),
    )
    report_path = tmp_path / "extract.json"
    write_json(report_to_dict(report), report_path)
    code = main(["--evaluate", str(EXAMPLE_GOLD), "--report", str(report_path)])
    assert code == 0
    payload = capsys.readouterr().out
    assert "unsupported_value_rate" in payload
    assert "reproduced_known_bad" in payload


PACK_GOLD = Path(__file__).resolve().parents[2] / "config" / "eval" / "gold.yaml"


def test_requires_llm_skipped_when_model_was_not_used() -> None:
    report = ExtractReport(job_id="eval-job", instrument_class="bond_exchange", llm_used=False)
    gold = [
        GoldField(
            field="issuer.name_full",
            label="accepted",
            value="ПАО «Пример»",
            requires_llm=True,
        )
    ]
    score = score_report(report, gold)
    assert score["labeled"] == 0
    assert score["misses"] == 0


def test_pack_gold_matches_path_and_currency() -> None:
    gold = load_gold(PACK_GOLD)
    fields = gold.fields_for(pack_path="/tmp/Биржевые облигации/Пример 1/docs")
    assert {item.field for item in fields} >= {"bond.currency.code", "cfi", "issuer.inn"}
    assert gold.fields_for(pack_path="/tmp/нет-такого-комплекта") == []

    report = ExtractReport(
        job_id="eval-job",
        instrument_class="bond_exchange",
        llm_used=False,
        fields=[
            FieldResult(
                field="bond.currency.code",
                raw_value="российских рублей",
                normalized_value="RUB",
                status="derived",
                evidence=[Evidence(source_id="src_1", quote="номинал 1000 российских рублей", page=1)],
            )
        ],
    )
    score = score_report(report, gold, pack_path="/data/Биржевые облигации/Пример 1")
    assert score["instrument_ok"] is True
    assert score["hits"] == 1
    assert score["unsupported_value_rate"] == 0.0
    assert score["misses"] == 0
