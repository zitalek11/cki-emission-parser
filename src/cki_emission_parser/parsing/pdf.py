from __future__ import annotations

from pathlib import Path

import pymupdf

from cki_emission_parser.models.types import BBox, ParsedDocument, SourceFragment
from cki_emission_parser.parsing.classify import classify_document
from cki_emission_parser.parsing.fragments import make_table_fragment, make_text_fragment
from cki_emission_parser.parsing.ocr import DisabledOcr, OcrBackend, page_needs_ocr


def parse_pdf(
    path: Path,
    *,
    document_id: str | None = None,
    ocr: OcrBackend | None = None,
) -> ParsedDocument:
    ocr = ocr or DisabledOcr()
    path = Path(path)
    document_id = document_id or path.stem
    doc = pymupdf.open(path)
    fragments: list[SourceFragment] = []
    warnings: list[str] = []
    ocr_pages: list[int] = []
    sample_parts: list[str] = []
    order = 0
    page_count = doc.page_count

    try:
        for page_index in range(page_count):
            page = doc[page_index]
            page_no = page_index + 1
            text = page.get_text("text") or ""
            need_ocr = page_needs_ocr(
                text_chars=len(text.strip()),
                image_count=len(page.get_images()),
                drawing_count=len(page.get_drawings()),
            )
            if need_ocr:
                ocr_pages.append(page_no)
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                ocr_text = ocr.ocr_page_image(pixmap.tobytes("png"))
                if ocr_text.strip():
                    order += 1
                    fragments.append(
                        make_text_fragment(
                            document_id=document_id,
                            document_name=path.name,
                            page=page_no,
                            order=order,
                            text=ocr_text,
                            bbox=None,
                            ocr=True,
                        )
                    )
                    sample_parts.append(ocr_text[:2000])
                else:
                    warnings.append(
                        f"Страница {page_no}: текстовый слой недостаточен, OCR не вернул текст"
                    )
                continue

            order, page_fragments = _extract_page_blocks(
                page=page,
                page_no=page_no,
                document_id=document_id,
                document_name=path.name,
                order=order,
            )
            fragments.extend(page_fragments)
            if text.strip():
                sample_parts.append(text[:2000])
    finally:
        doc.close()

    sample = "\n".join(sample_parts)
    doc_type, confidence = classify_document(sample, path.name)
    for fragment in fragments:
        fragment.document_type = doc_type

    return ParsedDocument(
        document_id=document_id,
        path=str(path),
        filename=path.name,
        media_type="pdf",
        document_type=doc_type,
        document_type_confidence=confidence,
        page_count=page_count,
        pages_needing_ocr=ocr_pages,
        parse_warnings=warnings,
        fragments=fragments,
    )


def _extract_page_blocks(
    *,
    page: pymupdf.Page,
    page_no: int,
    document_id: str,
    document_name: str,
    order: int,
) -> tuple[int, list[SourceFragment]]:
    fragments: list[SourceFragment] = []
    table_rects: list[pymupdf.Rect] = []

    for table_index, table in enumerate(_iter_tables(page), start=1):
        table_id = f"t{table_index:02d}"
        table_rects.append(pymupdf.Rect(table.bbox))
        rows = table.extract() or []
        headers = _table_headers(table, rows)
        for row_i, row in enumerate(rows):
            for col_i, cell in enumerate(row):
                text = "" if cell is None else str(cell).strip()
                if not text:
                    continue
                header = headers[col_i] if col_i < len(headers) else None
                order += 1
                fragments.append(
                    make_table_fragment(
                        document_id=document_id,
                        document_name=document_name,
                        page=page_no,
                        order=order,
                        text=f"{header}: {text}" if header else text,
                        table_id=table_id,
                        row=row_i,
                        column=col_i,
                        header=header,
                    )
                )

    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox_raw = block.get("bbox") or (0, 0, 0, 0)
        block_rect = pymupdf.Rect(bbox_raw)
        if _inside_table(block_rect, table_rects):
            continue
        lines: list[str] = []
        for line in block.get("lines", []):
            span_text = "".join(span.get("text", "") for span in line.get("spans", []))
            if span_text.strip():
                lines.append(span_text)
        text = "\n".join(lines).strip()
        if not text:
            continue
        order += 1
        fragments.append(
            make_text_fragment(
                document_id=document_id,
                document_name=document_name,
                page=page_no,
                order=order,
                text=text,
                bbox=BBox(x0=float(bbox_raw[0]), y0=float(bbox_raw[1]), x1=float(bbox_raw[2]), y1=float(bbox_raw[3])),
            )
        )
    return order, fragments


def _iter_tables(page: pymupdf.Page):
    try:
        finder = page.find_tables()
    except Exception:
        return []
    if finder is None:
        return []
    return getattr(finder, "tables", []) or []


def _table_headers(table: object, rows: list[list[object]]) -> list[str]:
    header = getattr(table, "header", None)
    names = getattr(header, "names", None) if header is not None else None
    if names:
        return [str(name) if name else f"col_{i}" for i, name in enumerate(names)]
    if rows:
        return [str(cell).strip() if cell else f"col_{i}" for i, cell in enumerate(rows[0])]
    return []


def _inside_table(block: pymupdf.Rect, tables: list[pymupdf.Rect]) -> bool:
    return any(block.intersects(table) and abs(block) <= abs(table) * 1.15 for table in tables)
