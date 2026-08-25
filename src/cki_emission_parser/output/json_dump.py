from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from cki_emission_parser.models.types import ExtractReport, IssueJob, ParsedDocument, RetrievalCandidate
from cki_emission_parser.output.review import review_queue


def job_to_dict(job: IssueJob, *, include_fragments: bool = True) -> dict:
    return {
        "job_id": job.job_id,
        "instrument_class": job.instrument_class,
        "allow_external_sources": job.allow_external_sources,
        "documents": [
            _document_to_dict(document, include_fragments=include_fragments)
            for document in job.documents
        ],
        "fragment_count": sum(len(document.fragments) for document in job.documents),
        "pages_needing_ocr": {
            document.filename: document.pages_needing_ocr
            for document in job.documents
            if document.pages_needing_ocr
        },
        "unknown_document_types": [
            document.filename
            for document in job.documents
            if document.document_type == "unknown"
        ],
    }


def report_to_dict(report: ExtractReport, *, include_retrieval: bool = False) -> dict:
    payload = {
        "job_id": report.job_id,
        "instrument_class": report.instrument_class,
        "llm_used": report.llm_used,
        "fields": [field.model_dump() for field in report.fields],
        "unmapped_facts": [fact.model_dump() for fact in report.unmapped_facts],
        "status_counts": dict(Counter(field.status for field in report.fields)),
        "review_queue": review_queue(report),
    }
    if include_retrieval:
        payload["retrieval"] = {
            field_id: [item.model_dump() for item in candidates]
            for field_id, candidates in report.retrieval.items()
        }
    return payload


def retrieval_to_dict(
    job_id: str,
    instrument_class: str,
    retrieval: dict[str, list[RetrievalCandidate]],
) -> dict:
    return {
        "job_id": job_id,
        "instrument_class": instrument_class,
        "hit_fields": [field_id for field_id, candidates in retrieval.items() if candidates],
        "retrieval": {
            field_id: [item.model_dump() for item in candidates]
            for field_id, candidates in retrieval.items()
        },
    }


def _document_to_dict(document: ParsedDocument, *, include_fragments: bool) -> dict:
    payload = {
        "document_id": document.document_id,
        "filename": document.filename,
        "path": document.path,
        "media_type": document.media_type,
        "document_type": document.document_type,
        "document_type_confidence": document.document_type_confidence,
        "page_count": document.page_count,
        "pages_needing_ocr": document.pages_needing_ocr,
        "parse_warnings": document.parse_warnings,
        "fragment_count": len(document.fragments),
    }
    if include_fragments:
        payload["fragments"] = [fragment.model_dump() for fragment in document.fragments]
    return payload


def write_json(payload: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_parse_report(job: IssueJob, path: Path, *, include_fragments: bool = True) -> None:
    write_json(job_to_dict(job, include_fragments=include_fragments), path)


def write_extract_report(
    report: ExtractReport,
    path: Path,
    *,
    include_retrieval: bool = False,
) -> None:
    write_json(report_to_dict(report, include_retrieval=include_retrieval), path)


def report_from_dict(payload: dict) -> ExtractReport:
    return ExtractReport.model_validate(
        {
            "job_id": payload.get("job_id") or "unknown",
            "instrument_class": payload.get("instrument_class") or "unknown",
            "llm_used": payload.get("llm_used", False),
            "fields": payload.get("fields") or [],
            "unmapped_facts": payload.get("unmapped_facts") or [],
            "retrieval": payload.get("retrieval") or {},
        }
    )
