from __future__ import annotations

from pathlib import Path

from cki_emission_parser.models.types import ParsedDocument
from cki_emission_parser.parsing.docx import parse_docx
from cki_emission_parser.parsing.ocr import OcrBackend
from cki_emission_parser.parsing.pdf import parse_pdf

_PDF = {".pdf"}
_DOCX = {".docx"}


def parse_file(
    path: Path,
    *,
    document_id: str | None = None,
    ocr: OcrBackend | None = None,
) -> ParsedDocument:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in _PDF:
        return parse_pdf(path, document_id=document_id, ocr=ocr)
    if suffix in _DOCX:
        return parse_docx(path, document_id=document_id)
    raise ValueError(f"Неподдерживаемый тип файла: {path.suffix}")
