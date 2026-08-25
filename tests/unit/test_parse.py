from pathlib import Path

from cki_emission_parser.ingestion import ingest_pack
from cki_emission_parser.parsing import parse_file
from cki_emission_parser.parsing.fragments import detect_section


def test_pdf_extracts_text_fragments_with_page_and_bbox(digital_pdf: Path) -> None:
    parsed = parse_file(digital_pdf)
    assert parsed.media_type == "pdf"
    assert parsed.page_count == 1
    assert parsed.pages_needing_ocr == []
    assert parsed.fragments
    assert parsed.fragments[0].page == 1
    assert parsed.fragments[0].bbox is not None
    blob = " ".join(fragment.text for fragment in parsed.fragments)
    assert "РЕШЕНИЕ О ВЫПУСКЕ" in blob
    assert parsed.document_type == "issuance_decision"


def test_scan_like_pdf_is_flagged_for_ocr(scan_like_pdf: Path) -> None:
    parsed = parse_file(scan_like_pdf)
    assert parsed.pages_needing_ocr == [1]
    assert parsed.fragments == []
    assert any("OCR" in warning for warning in parsed.parse_warnings)


def test_docx_keeps_paragraph_and_table_anchors(sample_docx: Path) -> None:
    parsed = parse_file(sample_docx)
    assert parsed.media_type == "docx"
    assert parsed.document_type == "placement_terms"
    texts = [fragment.text for fragment in parsed.fragments]
    assert any("условия размещения" in text.lower() for text in texts)
    table_fragments = [fragment for fragment in parsed.fragments if fragment.table]
    assert table_fragments
    assert table_fragments[0].table is not None
    assert table_fragments[0].source_id.endswith("_t01_r000_c00") or "_t01_" in table_fragments[0].source_id


def test_section_detector() -> None:
    assert detect_section("5.4. Номинальная стоимость") == "5.4"
    assert detect_section("Номинальная стоимость") is None


def test_ingest_pack_accepts_single_file(digital_pdf: Path) -> None:
    job = ingest_pack(digital_pdf)
    assert job.job_id == digital_pdf.stem
    assert len(job.documents) == 1
    assert job.allow_external_sources is False
