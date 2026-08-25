from __future__ import annotations

from pathlib import Path

from cki_emission_parser.models.types import IssueJob
from cki_emission_parser.parsing import parse_file
from cki_emission_parser.parsing.ocr import OcrBackend

_SUPPORTED = {".pdf", ".docx"}


def ingest_pack(path: Path, *, job_id: str | None = None, ocr: OcrBackend | None = None) -> IssueJob:
    path = Path(path)
    if path.is_file():
        files = [path]
        job_id = job_id or path.stem
    else:
        files = sorted(
            p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in _SUPPORTED
        )
        job_id = job_id or path.name
    documents = [
        parse_file(file_path, document_id=f"doc_{index:03d}", ocr=ocr)
        for index, file_path in enumerate(files, start=1)
    ]
    return IssueJob(job_id=job_id, documents=documents)
