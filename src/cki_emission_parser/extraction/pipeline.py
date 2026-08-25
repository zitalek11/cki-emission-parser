from __future__ import annotations

from cki_emission_parser.extraction.instrument import guess_instrument_class
from cki_emission_parser.extraction.llm import LlmProvider, NullLlmProvider
from cki_emission_parser.extraction.quote import quote_in_text, value_supported_by_quote
from cki_emission_parser.extraction.reconcile import group_by_document, reconcile_results
from cki_emission_parser.extraction.retrieve import retrieve_candidates, to_retrieval_candidates
from cki_emission_parser.extraction.unmapped import collect_unmapped_facts
from cki_emission_parser.extraction.verify import apply_verification
from cki_emission_parser.models.schema import ExtractSet, FieldSpec
from cki_emission_parser.models.types import (
    Evidence,
    ExtractReport,
    FieldProposal,
    FieldResult,
    InstrumentClass,
    IssueJob,
    RetrievalCandidate,
    SourceFragment,
)
from cki_emission_parser.normalize import apply_normalization, try_derive
from cki_emission_parser.schema import load_extract_set
from cki_emission_parser.validate import apply_validation


def extract_job(
    job: IssueJob,
    *,
    provider: LlmProvider | None = None,
    extract_set: ExtractSet | None = None,
    instrument_class: InstrumentClass | None = None,
) -> ExtractReport:
    extract_set = extract_set or load_extract_set()
    resolved_class = instrument_class or guess_instrument_class(job)
    job.instrument_class = resolved_class
    llm = provider or NullLlmProvider()
    llm_used = not isinstance(llm, NullLlmProvider)
    fields: list[FieldResult] = []
    retrieval: dict[str, list[RetrievalCandidate]] = {}

    for spec in extract_set.for_instrument(resolved_class):
        pairs = retrieve_candidates(job, spec)
        retrieval[spec.id] = to_retrieval_candidates(pairs)
        if not pairs:
            fields.append(_empty(spec, "нет кандидатов в тексте комплекта"))
            continue
        grouped = group_by_document(pairs)
        per_document: list[FieldResult] = []
        all_fragments = [fragment for fragment, _ in pairs]
        for doc_pairs in grouped.values():
            fragments = [fragment for fragment, _ in doc_pairs]
            result = _extract_from_fragments(
                spec,
                fragments,
                llm=llm,
                llm_used=llm_used,
                instrument_class=resolved_class,
            )
            result = apply_normalization(spec, result)
            result = apply_validation(spec, result, fragments)
            result = apply_verification(spec, result, fragments)
            per_document.append(result)
        fields.append(reconcile_results(spec, per_document, all_fragments))

    return ExtractReport(
        job_id=job.job_id,
        instrument_class=resolved_class,
        llm_used=llm_used,
        fields=fields,
        unmapped_facts=collect_unmapped_facts(job, extract_set),
        retrieval=retrieval,
    )


def _extract_from_fragments(
    spec: FieldSpec,
    fragments: list[SourceFragment],
    *,
    llm: LlmProvider,
    llm_used: bool,
    instrument_class: InstrumentClass,
) -> FieldResult:
    if llm_used:
        proposal = llm.extract_field(spec, fragments, instrument_class=instrument_class)
        result = _accept_proposal(spec, proposal, fragments)
    else:
        result = _empty(spec, "LLM не задан; заполнение без модели запрещено")
    if result.status == "not_found":
        derived = try_derive(spec, fragments)
        if derived is not None:
            return derived
    return result


def _accept_proposal(
    spec: FieldSpec,
    proposal: FieldProposal,
    fragments: list[SourceFragment],
) -> FieldResult:
    if (
        proposal.value is None
        or not (proposal.quote or "").strip()
        or not (proposal.evidence_source_id or "").strip()
    ):
        return _empty(spec, proposal.reason or "модель не указала значение и цитату")

    by_id = {fragment.source_id: fragment for fragment in fragments}
    fragment = by_id.get(proposal.evidence_source_id)
    if fragment is None:
        return _empty(spec, "evidence_source_id не входит в список кандидатов")
    if not quote_in_text(proposal.quote, fragment.text):
        return _empty(spec, "цитата не найдена в указанном фрагменте")
    if not value_supported_by_quote(proposal.value, proposal.quote, fragment.text):
        return _empty(spec, "значение не подтверждается цитатой")

    evidence = Evidence(
        source_id=fragment.source_id,
        quote=proposal.quote,
        page=fragment.page,
        section=fragment.section,
    )
    status = "ambiguous" if proposal.ambiguous else "confirmed"
    return FieldResult(
        field=spec.id,
        raw_value=proposal.value,
        status=status,
        evidence=[evidence],
        canonical_source=fragment.source_id,
        extraction_method="direct",
        quality_score=0.7 if status == "confirmed" else 0.4,
        review_decision="accepted" if status == "confirmed" else "review_required",
        reason=proposal.reason,
    )


def _empty(spec: FieldSpec, reason: str) -> FieldResult:
    return FieldResult(field=spec.id, status="not_found", reason=reason)
