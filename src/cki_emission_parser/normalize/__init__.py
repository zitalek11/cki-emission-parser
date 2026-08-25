from __future__ import annotations

from cki_emission_parser.models.schema import FieldSpec
from cki_emission_parser.models.types import DateValue, FieldResult
from cki_emission_parser.normalize.derive import try_derive
from cki_emission_parser.normalize.values import CannotNormalize, normalize_value

__all__ = ["apply_normalization", "try_derive"]


def apply_normalization(spec: FieldSpec, result: FieldResult) -> FieldResult:
    if result.status not in {"confirmed", "derived", "ambiguous"} or result.raw_value is None:
        return result
    quote = result.evidence[0].quote if result.evidence else ""
    try:
        normalized = normalize_value(spec, result.raw_value, quote)
    except (CannotNormalize, ValueError) as exc:
        return _reject(spec, f"нормализация: {exc}")
    update: dict = {"normalized_value": _dump(normalized)}
    if isinstance(normalized, DateValue) and normalized.date_kind == "rule":
        update["raw_value"] = normalized.raw_text
        update["reason"] = _join_reason(
            result.reason,
            "правило даты сохранено, календарь не вычислялся",
        )
    return result.model_copy(update=update)


def _dump(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value


def _reject(spec: FieldSpec, reason: str) -> FieldResult:
    return FieldResult(
        field=spec.id,
        status="not_found",
        reason=reason,
        review_decision="rejected",
    )


def _join_reason(current: str | None, extra: str) -> str:
    if not current:
        return extra
    if extra in current:
        return current
    return f"{current}; {extra}"
