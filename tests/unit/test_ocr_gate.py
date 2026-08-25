from cki_emission_parser.parsing.ocr import page_needs_ocr


def test_digital_text_does_not_need_ocr() -> None:
    assert page_needs_ocr(text_chars=400, image_count=2, drawing_count=0) is False


def test_empty_page_with_image_needs_ocr() -> None:
    assert page_needs_ocr(text_chars=0, image_count=1, drawing_count=0) is True


def test_sparse_text_without_graphics_needs_ocr() -> None:
    assert page_needs_ocr(text_chars=0, image_count=0, drawing_count=0) is True


def test_short_header_only_with_drawing_needs_ocr() -> None:
    assert page_needs_ocr(text_chars=12, image_count=0, drawing_count=3) is True
