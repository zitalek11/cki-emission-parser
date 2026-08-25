from __future__ import annotations

from cki_emission_parser.extraction.instrument import guess_instrument_class
from cki_emission_parser.extraction.quote import normalize_match_text
from cki_emission_parser.models.schema import ExtractSet, FieldSpec
from cki_emission_parser.models.types import (
    InstrumentClass,
    IssueJob,
    RetrievalCandidate,
    SourceFragment,
)
from cki_emission_parser.schema import load_extract_set

DEFAULT_TOP_K = 8


def iter_fragments(job: IssueJob) -> list[SourceFragment]:
    fragments: list[SourceFragment] = []
    for document in job.documents:
        fragments.extend(document.fragments)
    return fragments


def retrieve_candidates(
    job: IssueJob,
    field: FieldSpec,
    *,
    top_k: int = DEFAULT_TOP_K,
) -> list[tuple[SourceFragment, float]]:
    scored: list[tuple[SourceFragment, float]] = []
    for fragment in iter_fragments(job):
        score = _score_fragment(fragment, field)
        if score > 0:
            scored.append((fragment, score))
    scored.sort(key=lambda item: (-item[1], item[0].order))
    return scored[:top_k]


def retrieve_job(
    job: IssueJob,
    *,
    extract_set: ExtractSet | None = None,
    instrument_class: InstrumentClass | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[InstrumentClass, dict[str, list[RetrievalCandidate]]]:
    extract_set = extract_set or load_extract_set()
    resolved = instrument_class or guess_instrument_class(job)
    retrieval = {
        spec.id: to_retrieval_candidates(retrieve_candidates(job, spec, top_k=top_k))
        for spec in extract_set.for_instrument(resolved)
    }
    return resolved, retrieval


def to_retrieval_candidates(pairs: list[tuple[SourceFragment, float]]) -> list[RetrievalCandidate]:
    return [
        RetrievalCandidate(
            source_id=fragment.source_id,
            score=round(score, 3),
            document_type=fragment.document_type,
            page=fragment.page,
            snippet=fragment.text[:280],
        )
        for fragment, score in pairs
    ]


def _score_fragment(fragment: SourceFragment, field: FieldSpec) -> float:
    text = normalize_match_text(fragment.text)
    if not text:
        return 0.0
    score = 0.0
    for synonym in field.synonyms:
        needle = normalize_match_text(synonym)
        if needle and needle in text:
            score += 2.0 + 0.15 * len(needle.split())
    if score == 0:
        return 0.0
    preferred = set(field.preferred_documents)
    if preferred and fragment.document_type in preferred:
        score += 1.5
    if field.id.startswith("issuer.") and fragment.page is not None and fragment.page <= 2:
        score += 0.3
    return score
