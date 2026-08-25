from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from cki_emission_parser.eval.gold import GoldField, GoldFile
from cki_emission_parser.models.types import ExtractReport, FieldResult

_EMPTY_STATUSES = {"not_found", "not_applicable"}


def load_gold(path: Path) -> GoldFile:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return GoldFile.model_validate(data)


def has_extracted_value(field: FieldResult | None) -> bool:
    if field is None or field.status in _EMPTY_STATUSES:
        return False
    value = field.normalized_value if field.normalized_value is not None else field.raw_value
    if value is None or value == "" or value == []:
        return False
    return True


def score_report(
    report: ExtractReport,
    gold: GoldFile | list[GoldField],
    *,
    pack_path: str | None = None,
    pack_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(gold, GoldFile):
        specs = gold.fields_for(pack_path=pack_path, pack_id=pack_id)
        expected_class = _expected_instrument(gold, pack_path=pack_path, pack_id=pack_id)
    else:
        specs = list(gold)
        expected_class = None
    if not report.llm_used:
        specs = [spec for spec in specs if not spec.requires_llm]
    by_id = {field.field: field for field in report.fields}
    rows: list[dict[str, Any]] = []
    for spec in specs:
        rows.append(_score_field(spec, by_id.get(spec.field)))

    produced = [row for row in rows if row["produced"]]
    unsupported = [row for row in rows if row["unsupported"]]
    produced_count = len(produced)
    unsupported_count = len(unsupported)
    rate = (unsupported_count / produced_count) if produced_count else 0.0

    slice_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = row["slice"] or "unspecified"
        slice_rows.setdefault(key, []).append(row)

    return {
        "job_id": report.job_id,
        "unsupported_value_rate": rate,
        "produced": produced_count,
        "unsupported": unsupported_count,
        "hits": sum(1 for row in rows if row["outcome"] == "hit"),
        "misses": sum(1 for row in rows if row["outcome"] == "miss"),
        "false_fills": sum(1 for row in rows if row["outcome"] == "false_fill"),
        "wrong_values": sum(1 for row in rows if row["outcome"] == "wrong_value"),
        "reproduced_known_bad": sum(1 for row in rows if row["outcome"] == "reproduced_known_bad"),
        "labeled": len(rows),
        "instrument_class": report.instrument_class,
        "instrument_ok": expected_class is None or expected_class == report.instrument_class,
        "expected_instrument_class": expected_class,
        "outcomes": dict(Counter(row["outcome"] for row in rows)),
        "by_slice": {
            name: _slice_summary(items) for name, items in slice_rows.items()
        },
        "details": rows,
    }


def _expected_instrument(
    gold: GoldFile,
    *,
    pack_path: str | None,
    pack_id: str | None,
) -> str | None:
    path_s = (pack_path or "").replace("\\", "/")
    for pack in gold.packs:
        if pack_id and pack.id == pack_id:
            return pack.instrument_class
        if pack.match and pack.match in path_s:
            return pack.instrument_class
    return None


def _slice_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    produced = sum(1 for row in rows if row["produced"])
    unsupported = sum(1 for row in rows if row["unsupported"])
    return {
        "labeled": len(rows),
        "produced": produced,
        "unsupported": unsupported,
        "unsupported_value_rate": (unsupported / produced) if produced else 0.0,
        "outcomes": dict(Counter(row["outcome"] for row in rows)),
    }


def _score_field(spec: GoldField, field: FieldResult | None) -> dict[str, Any]:
    produced = has_extracted_value(field)
    system_value = None
    system_status = None
    if field is not None:
        system_status = field.status
        system_value = field.normalized_value if field.normalized_value is not None else field.raw_value

    outcome, unsupported, reason = _classify(spec, field, produced, system_value)
    return {
        "field": spec.field,
        "label": spec.label,
        "slice": spec.slice,
        "outcome": outcome,
        "produced": produced,
        "unsupported": unsupported,
        "system_status": system_status,
        "system_value": system_value,
        "expected_value": spec.value,
        "reason": reason,
    }


def _classify(
    spec: GoldField,
    field: FieldResult | None,
    produced: bool,
    system_value: object,
) -> tuple[str, bool, str]:
    if spec.label == "accepted":
        if not produced:
            return "miss", False, spec.reason or "принятое значение не извлечено"
        if not _values_equal(spec.value, system_value):
            return "wrong_value", True, spec.reason or "значение не совпало с принятым"
        if spec.quote_contains and not _quote_contains(field, spec.quote_contains):
            return "unsupported_quote", True, "значение есть, но цитата не подтверждает его"
        if field is None or not field.evidence:
            return "unsupported_quote", True, "значение без цитаты"
        return "hit", False, spec.reason or "совпало с принятым эталоном"

    if spec.label == "must-be-empty":
        if produced:
            return "false_fill", True, spec.reason or "поле должно остаться пустым"
        return "ok_empty", False, spec.reason or "пусто, как и требуется"

    if produced and spec.value is not None and _values_equal(spec.value, system_value):
        return "reproduced_known_bad", True, spec.reason or "повторён заведомо плохой разбор"
    if produced:
        return "false_fill", True, spec.reason or "поле не подтверждено в документе"
    return "ok_empty", False, spec.reason or "плохой Excel-разбор не повторён"


def _quote_contains(field: FieldResult | None, needle: str) -> bool:
    if field is None:
        return False
    needle_n = " ".join(needle.split()).casefold()
    return any(needle_n in " ".join(item.quote.split()).casefold() for item in field.evidence)


def _values_equal(expected: object, actual: object) -> bool:
    if expected is None:
        return actual is None
    if isinstance(expected, dict) and isinstance(actual, dict):
        if "date_kind" in expected:
            if expected.get("date_kind") != actual.get("date_kind"):
                return False
            if expected.get("normalized") and expected.get("normalized") == actual.get("normalized"):
                return True
            return _norm_text(expected.get("raw_text")) == _norm_text(actual.get("raw_text"))
        if "amount" in expected:
            return expected.get("amount") == actual.get("amount") and _norm_text(
                expected.get("currency")
            ) == _norm_text(actual.get("currency"))
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return expected == actual
    return _norm_text(expected) == _norm_text(actual)


def _norm_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("«", "\"").replace("»", "\"").split()).casefold()
