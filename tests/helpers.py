from __future__ import annotations

from cki_emission_parser.models.schema import ExtractSet, FieldSpec
from cki_emission_parser.models.types import DocumentType, IssueJob, ParsedDocument, SourceFragment


def build_job(
    text: str,
    *,
    filename: str = "issuance_decision.pdf",
    document_type: DocumentType = "issuance_decision",
    source_id: str = "src_001",
    job_id: str = "test-job",
) -> IssueJob:
    fragment = SourceFragment(
        source_id=source_id,
        document_id="doc_001",
        document_name=filename,
        document_type=document_type,
        page=1,
        order=0,
        text=text,
    )
    return IssueJob(
        job_id=job_id,
        documents=[
            ParsedDocument(
                document_id="doc_001",
                path=filename,
                filename=filename,
                media_type="pdf",
                document_type=document_type,
                page_count=1,
                fragments=[fragment],
            )
        ],
    )


def add_document(
    job: IssueJob,
    text: str,
    *,
    document_id: str,
    filename: str,
    document_type: DocumentType,
    source_id: str,
) -> IssueJob:
    fragment = SourceFragment(
        source_id=source_id,
        document_id=document_id,
        document_name=filename,
        document_type=document_type,
        page=1,
        order=0,
        text=text,
    )
    job.documents.append(
        ParsedDocument(
            document_id=document_id,
            path=filename,
            filename=filename,
            media_type="pdf",
            document_type=document_type,
            page_count=1,
            fragments=[fragment],
        )
    )
    return job


def field_spec(**overrides: object) -> FieldSpec:
    data: dict = {
        "id": "issuer.name_full",
        "nrd_path": "issuer.name_full",
        "title": "Полное фирменное наименование эмитента",
        "type": "string",
        "applies_to": ["share_common", "share_pref", "bond_exchange", "bond_structured"],
        "synonyms": ["полное фирменное наименование"],
        "preferred_documents": ["issuance_decision"],
    }
    data.update(overrides)
    return FieldSpec.model_validate(data)


def mini_set(*fields: FieldSpec, instrument_class: str = "bond_exchange") -> ExtractSet:
    return ExtractSet(version=1, instrument_classes=[instrument_class], fields=list(fields))
