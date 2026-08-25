from __future__ import annotations

from cki_emission_parser.extraction.quote import quote_in_text, value_supported_by_quote
from cki_emission_parser.models.schema import FieldSpec
from cki_emission_parser.models.types import FieldResult, SourceFragment


def apply_verification(
    spec: FieldSpec,
    result: FieldResult,
    fragments: list[SourceFragment],
) -> FieldResult:
    """Повторная проверка: цитата всё ещё в фрагменте, значение из неё следует."""
    if result.status not in {"confirmed", "derived", "ambiguous"}:
        return result
    if not result.evidence:
        return _reject(spec, "нет цитаты для повторной проверки")

    by_id = {fragment.source_id: fragment for fragment in fragments}
    for item in result.evidence:
        fragment = by_id.get(item.source_id)
        if fragment is None:
            return _reject(spec, "source_id цитаты не найден среди фрагментов")
        if not quote_in_text(item.quote, fragment.text):
            return _reject(spec, "повторная проверка: цитата не найдена в фрагменте")
        if not _value_holds(result, item.quote, fragment.text):
            return _reject(spec, "повторная проверка: значение не следует из цитаты")
    return result


def _value_holds(result: FieldResult, quote: str, fragment_text: str) -> bool:
    if result.raw_value is not None and not isinstance(result.raw_value, (list, dict)):
        if value_supported_by_quote(result.raw_value, quote, fragment_text):
            return True
    normalized = result.normalized_value
    if isinstance(normalized, dict):
        raw_text = normalized.get("raw_text")
        if raw_text and (
            quote_in_text(str(raw_text), fragment_text)
            or quote_in_text(str(raw_text), quote)
        ):
            return True
        amount = normalized.get("amount")
        if amount is not None and value_supported_by_quote(amount, quote, fragment_text):
            return True
        iso = normalized.get("normalized")
        if iso and value_supported_by_quote(iso, quote, fragment_text):
            return True
        return bool(raw_text)
    if normalized is not None and not isinstance(normalized, list):
        return value_supported_by_quote(normalized, quote, fragment_text)
    return result.raw_value is None


def _reject(spec: FieldSpec, reason: str) -> FieldResult:
    return FieldResult(
        field=spec.id,
        status="not_found",
        reason=reason,
        review_decision="rejected",
    )
