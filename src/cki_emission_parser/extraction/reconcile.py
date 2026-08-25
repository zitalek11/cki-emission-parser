from __future__ import annotations

from cki_emission_parser.extraction.quote import normalize_match_text
from cki_emission_parser.models.schema import FieldSpec
from cki_emission_parser.models.types import Evidence, FieldResult, SourceFragment


def group_by_document(
    pairs: list[tuple[SourceFragment, float]],
) -> dict[str, list[tuple[SourceFragment, float]]]:
    grouped: dict[str, list[tuple[SourceFragment, float]]] = {}
    for fragment, score in pairs:
        grouped.setdefault(fragment.document_id, []).append((fragment, score))
    return grouped


def reconcile_results(
    spec: FieldSpec,
    results: list[FieldResult],
    fragments: list[SourceFragment] | None = None,
) -> FieldResult:
    alive = [item for item in results if item.status in {"confirmed", "derived", "ambiguous"}]
    if not alive:
        return results[0] if results else FieldResult(field=spec.id, status="not_found")
    if len(alive) == 1:
        return alive[0]

    buckets: dict[tuple, list[FieldResult]] = {}
    for item in alive:
        buckets.setdefault(_comparable(item), []).append(item)
    by_id = {fragment.source_id: fragment for fragment in fragments or []}
    if len(buckets) == 1:
        return _merge_agreeing(spec, alive, by_id)

    evidence: list[Evidence] = []
    sources: list[str] = []
    values: list[object] = []
    for item in alive:
        evidence.extend(item.evidence)
        if item.canonical_source:
            sources.append(item.canonical_source)
        values.append(
            item.normalized_value if item.normalized_value is not None else item.raw_value
        )
    return FieldResult(
        field=spec.id,
        raw_value=values,
        normalized_value=values,
        status="conflict",
        evidence=evidence,
        supporting_sources=sources,
        extraction_method=alive[0].extraction_method,
        quality_score=0.3,
        review_decision="review_required",
        reason="документы комплекта дают несовместимые значения; обе цитаты сохранены",
    )


def _merge_agreeing(
    spec: FieldSpec,
    results: list[FieldResult],
    by_id: dict[str, SourceFragment],
) -> FieldResult:
    preferred = spec.preferred_documents
    chosen = results[0]
    for wanted in preferred:
        for item in results:
            if _document_type(item, by_id) == wanted:
                chosen = item
                break
        else:
            continue
        break
    evidence: list[Evidence] = []
    sources: list[str] = []
    seen: set[str] = set()
    for item in results:
        for piece in item.evidence:
            key = f"{piece.source_id}:{piece.quote}"
            if key in seen:
                continue
            seen.add(key)
            evidence.append(piece)
        if item.canonical_source:
            sources.append(item.canonical_source)
    extra = [source for source in sources if source != chosen.canonical_source]
    return chosen.model_copy(
        update={
            "evidence": evidence,
            "supporting_sources": extra,
            "quality_score": max(chosen.quality_score, 0.75),
        }
    )


def _document_type(result: FieldResult, by_id: dict[str, SourceFragment]) -> str | None:
    if not result.evidence:
        return None
    fragment = by_id.get(result.evidence[0].source_id)
    return None if fragment is None else fragment.document_type


def _comparable(result: FieldResult) -> tuple:
    value = result.normalized_value if result.normalized_value is not None else result.raw_value
    if isinstance(value, dict):
        if "amount" in value:
            return ("money", value.get("amount"), value.get("currency"))
        if "date_kind" in value:
            return (
                "date",
                value.get("date_kind"),
                value.get("normalized") or normalize_match_text(str(value.get("raw_text") or "")),
            )
        return ("dict", tuple(sorted((str(key), str(val)) for key, val in value.items())))
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return ("num", float(value))
    return ("str", normalize_match_text(str(value or "")))
