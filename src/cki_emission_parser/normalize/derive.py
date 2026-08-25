from __future__ import annotations

from cki_emission_parser.models.schema import FieldSpec
from cki_emission_parser.models.types import Evidence, FieldResult, SourceFragment
from cki_emission_parser.normalize.values import currency_match_span


def try_derive(spec: FieldSpec, fragments: list[SourceFragment]) -> FieldResult | None:
    if not spec.allow_derivation or not spec.derivation_rule:
        return None
    if spec.derivation_rule == "currency_from_text":
        return _derive_currency(spec, fragments)
    return None


def _derive_currency(spec: FieldSpec, fragments: list[SourceFragment]) -> FieldResult | None:
    for fragment in fragments:
        match = currency_match_span(fragment.text)
        if not match:
            continue
        code, phrase = match
        quote = _window(fragment.text, phrase)
        evidence = Evidence(
            source_id=fragment.source_id,
            quote=quote,
            page=fragment.page,
            section=fragment.section,
        )
        return FieldResult(
            field=spec.id,
            raw_value=phrase,
            normalized_value=code,
            status="derived",
            evidence=[evidence],
            canonical_source=fragment.source_id,
            extraction_method="derived",
            derivation_rule="currency_from_text",
            quality_score=0.6,
            review_decision="accepted",
            reason="валюта по правилу currency_from_text",
        )
    return None


def _window(text: str, phrase: str, *, radius: int = 48) -> str:
    start = text.casefold().find(phrase.casefold())
    if start < 0:
        return phrase
    left = max(0, start - radius)
    right = min(len(text), start + len(phrase) + radius)
    return text[left:right].strip()
