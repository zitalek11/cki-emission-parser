from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from cki_emission_parser.models.types import ParsedDocument, SourceFragment
from cki_emission_parser.parsing.classify import classify_document
from cki_emission_parser.parsing.fragments import make_table_fragment, make_text_fragment


def parse_docx(path: Path, *, document_id: str | None = None) -> ParsedDocument:
    path = Path(path)
    document_id = document_id or path.stem
    document = Document(str(path))
    fragments: list[SourceFragment] = []
    warnings: list[str] = [
        "DOCX не имеет страниц; якоря — абзац и ячейка таблицы. Для страниц конвертируйте в PDF."
    ]
    sample_parts: list[str] = []
    order = 0
    table_index = 0

    for block in _iter_body_blocks(document):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            order += 1
            fragments.append(
                make_text_fragment(
                    document_id=document_id,
                    document_name=path.name,
                    page=None,
                    order=order,
                    text=text,
                    bbox=None,
                )
            )
            sample_parts.append(text)
        elif isinstance(block, Table):
            table_index += 1
            table_id = f"t{table_index:02d}"
            headers = [_cell_text(cell) for cell in block.rows[0].cells] if block.rows else []
            for row_i, row in enumerate(block.rows):
                for col_i, cell in enumerate(row.cells):
                    text = _cell_text(cell)
                    if not text:
                        continue
                    header = headers[col_i] if col_i < len(headers) else None
                    order += 1
                    fragments.append(
                        make_table_fragment(
                            document_id=document_id,
                            document_name=path.name,
                            page=None,
                            order=order,
                            text=f"{header}: {text}" if header and row_i > 0 else text,
                            table_id=table_id,
                            row=row_i,
                            column=col_i,
                            header=header if row_i > 0 else None,
                        )
                    )
                    sample_parts.append(text)

    sample = "\n".join(sample_parts[:80])
    doc_type, confidence = classify_document(sample, path.name)
    for fragment in fragments:
        fragment.document_type = doc_type

    return ParsedDocument(
        document_id=document_id,
        path=str(path),
        filename=path.name,
        media_type="docx",
        document_type=doc_type,
        document_type_confidence=confidence,
        page_count=0,
        pages_needing_ocr=[],
        parse_warnings=warnings,
        fragments=fragments,
    )


def _iter_body_blocks(document: Document):
    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _cell_text(cell) -> str:
    return " ".join(cell.text.split()).strip()
