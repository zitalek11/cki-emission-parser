from __future__ import annotations

# Страница считается нуждающейся в OCR, если текстовый слой слишком беден
# при наличии графики либо при большом размере страницы без текста.

MIN_TEXT_CHARS = 40


def page_needs_ocr(*, text_chars: int, image_count: int, drawing_count: int = 0) -> bool:
    if text_chars >= MIN_TEXT_CHARS:
        return False
    if image_count > 0 or drawing_count > 0:
        return True
    return text_chars == 0


class OcrBackend:
    """Интерфейс OCR. Реализации подключаются отдельно; отсутствие OCR не роняет разбор."""

    def ocr_page_image(self, image_bytes: bytes) -> str:
        raise NotImplementedError


class DisabledOcr(OcrBackend):
    def ocr_page_image(self, image_bytes: bytes) -> str:
        return ""
