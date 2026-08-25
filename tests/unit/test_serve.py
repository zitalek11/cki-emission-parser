from pathlib import Path

from cki_emission_parser.serve import extract_to_html, index_html


def test_index_explains_missing_model() -> None:
    page = index_html()
    assert "Локальный разбор выпуска" in page
    assert "CKI_LLM_API_KEY" in page or "Модель подключена" in page


def test_extract_to_html_from_digital_pdf(digital_pdf: Path, monkeypatch) -> None:
    monkeypatch.setenv("CKI_LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    page = extract_to_html(digital_pdf)
    assert "Ревью извлечения" in page
    assert "bond_exchange" in page or "share_" in page
    assert "LLM" in page
