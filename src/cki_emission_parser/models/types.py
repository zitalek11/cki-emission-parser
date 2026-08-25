from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

InstrumentClass = Literal[
    "share_common",
    "share_pref",
    "bond_exchange",
    "bond_structured",
    "unknown",
]

DocumentType = Literal[
    "issuance_decision",
    "placement_terms",
    "bond_program",
    "prospectus",
    "issuance_results",
    "notice",
    "unknown",
]

FieldStatus = Literal[
    "confirmed",
    "derived",
    "ambiguous",
    "conflict",
    "not_found",
    "not_applicable",
]

DateKind = Literal["exact", "rule", "relative", "range"]

ReviewDecision = Literal["accepted", "review_required", "rejected"]


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class TableCellRef(BaseModel):
    table_id: str
    row: int
    column: int
    header: str | None = None


class SourceFragment(BaseModel):
    source_id: str
    document_id: str
    document_name: str
    document_type: DocumentType = "unknown"
    page: int | None = None
    section: str | None = None
    order: int = 0
    text: str
    bbox: BBox | None = None
    table: TableCellRef | None = None
    ocr: bool = False


class Evidence(BaseModel):
    source_id: str
    quote: str
    page: int | None = None
    section: str | None = None


class MoneyValue(BaseModel):
    amount: float
    currency: str | None = None
    raw_text: str


class DateValue(BaseModel):
    date_kind: DateKind
    raw_text: str
    normalized: str | None = None


class FieldResult(BaseModel):
    field: str
    raw_value: Any | None = None
    normalized_value: Any | None = None
    status: FieldStatus = "not_found"
    evidence: list[Evidence] = Field(default_factory=list)
    canonical_source: str | None = None
    supporting_sources: list[str] = Field(default_factory=list)
    extraction_method: Literal["direct", "derived"] | None = None
    derivation_rule: str | None = None
    quality_score: float = 0.0
    review_decision: ReviewDecision = "review_required"
    reason: str | None = None


class RetrievalCandidate(BaseModel):
    source_id: str
    score: float
    document_type: DocumentType = "unknown"
    page: int | None = None
    snippet: str


class FieldProposal(BaseModel):
    """Ответ модели до проверки цитаты кодом. Статус поля ставит пайплайн, не модель."""

    model_config = ConfigDict(extra="ignore")

    value: Any | None = None
    evidence_source_id: str | None = None
    quote: str | None = None
    ambiguous: bool = False
    reason: str | None = None


class UnmappedFact(BaseModel):
    type: Literal["unmapped_fact"] = "unmapped_fact"
    label: str
    value: str
    source: Evidence
    possible_field: str | None = None


class ExtractReport(BaseModel):
    job_id: str
    instrument_class: InstrumentClass = "unknown"
    llm_used: bool = False
    fields: list[FieldResult] = Field(default_factory=list)
    unmapped_facts: list[UnmappedFact] = Field(default_factory=list)
    retrieval: dict[str, list[RetrievalCandidate]] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    document_id: str
    path: str
    filename: str
    media_type: Literal["pdf", "docx", "xlsx", "unknown"]
    document_type: DocumentType = "unknown"
    document_type_confidence: float = 0.0
    page_count: int = 0
    pages_needing_ocr: list[int] = Field(default_factory=list)
    parse_warnings: list[str] = Field(default_factory=list)
    fragments: list[SourceFragment] = Field(default_factory=list)


class IssueJob(BaseModel):
    job_id: str
    instrument_class: InstrumentClass = "unknown"
    allow_external_sources: bool = False
    documents: list[ParsedDocument] = Field(default_factory=list)
