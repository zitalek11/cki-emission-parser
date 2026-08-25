from __future__ import annotations

import re

from cki_emission_parser.models.types import BBox, SourceFragment, TableCellRef

_SECTION = re.compile(
    r"^(?P<section>\d+(?:\.\d+){0,6})\.?\s+\S",
)


def detect_section(text: str) -> str | None:
    stripped = text.strip()
    match = _SECTION.match(stripped)
    if match:
        return match.group("section")
    return None


def make_text_fragment(
    *,
    document_id: str,
    document_name: str,
    page: int | None,
    order: int,
    text: str,
    bbox: BBox | None,
    section: str | None = None,
    ocr: bool = False,
) -> SourceFragment:
    page_part = f"p{page:03d}" if page is not None else "p000"
    source_id = f"{document_id}_{page_part}_b{order:04d}"
    return SourceFragment(
        source_id=source_id,
        document_id=document_id,
        document_name=document_name,
        page=page,
        section=section or detect_section(text),
        order=order,
        text=text.strip(),
        bbox=bbox,
        ocr=ocr,
    )


def make_table_fragment(
    *,
    document_id: str,
    document_name: str,
    page: int | None,
    order: int,
    text: str,
    table_id: str,
    row: int,
    column: int,
    header: str | None,
    bbox: BBox | None = None,
    section: str | None = None,
) -> SourceFragment:
    page_part = f"p{page:03d}" if page is not None else "p000"
    source_id = f"{document_id}_{page_part}_{table_id}_r{row:03d}_c{column:02d}"
    return SourceFragment(
        source_id=source_id,
        document_id=document_id,
        document_name=document_name,
        page=page,
        section=section,
        order=order,
        text=text.strip(),
        bbox=bbox,
        table=TableCellRef(
            table_id=table_id,
            row=row,
            column=column,
            header=header,
        ),
    )
