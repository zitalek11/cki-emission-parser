from __future__ import annotations

import json
from typing import Any

from cki_emission_parser.models.types import ExtractReport, FieldResult

_STATUS_RU = {
    "confirmed": "Подтверждено",
    "derived": "Выведено правилом",
    "ambiguous": "Неоднозначно",
    "conflict": "Конфликт",
    "not_found": "Не найдено",
    "not_applicable": "Не применимо",
}

_REVIEW_RU = {
    "accepted": "Принято",
    "review_required": "Нужна проверка",
    "rejected": "Отклонено",
}

_REVIEW_STATUSES = {"conflict", "ambiguous"}


def status_label_ru(status: str) -> str:
    return _STATUS_RU.get(status, status)


def review_label_ru(decision: str) -> str:
    return _REVIEW_RU.get(decision, decision)


def needs_review(field: FieldResult) -> bool:
    return field.status in _REVIEW_STATUSES or field.review_decision == "review_required"


def review_queue(report: ExtractReport) -> dict[str, Any]:
    queued = [field.field for field in report.fields if needs_review(field)]
    return {
        "field_ids": queued,
        "conflict_count": sum(1 for field in report.fields if field.status == "conflict"),
        "unmapped_count": len(report.unmapped_facts),
    }


def format_display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "да" if value else "нет"
    if isinstance(value, list):
        return " | ".join(format_display_value(item) for item in value if item is not None)
    if isinstance(value, dict):
        if "date_kind" in value:
            if value.get("date_kind") == "rule":
                raw = value.get("raw_text") or ""
                return f"правило: {raw}".strip()
            return str(value.get("normalized") or value.get("raw_text") or "")
        if "amount" in value:
            amount = value.get("amount")
            currency = value.get("currency") or ""
            return f"{amount} {currency}".strip()
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def primary_quote(field: FieldResult) -> str:
    if not field.evidence:
        return ""
    return field.evidence[0].quote


def quotes_joined(field: FieldResult) -> str:
    return " || ".join(item.quote for item in field.evidence if item.quote)


def primary_page(field: FieldResult) -> int | None:
    if not field.evidence:
        return None
    return field.evidence[0].page
