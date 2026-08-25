from __future__ import annotations

import re

from cki_emission_parser.models.types import DocumentType
from cki_emission_parser.schema.loader import load_document_types

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    text = text.replace("+", " ").replace("_", " ").replace("-", " ")
    return _WS.sub(" ", text.casefold()).strip()


def classify_document(text_sample: str, filename: str = "") -> tuple[DocumentType, float]:
    """Эвристика по тексту и имени файла. Не завязана на эмитента.

    Совпадения в имени файла и в начале документа весят больше, чем упоминания
    в определениях («решение о выпуске» внутри программы облигаций).
    """
    filename_n = _norm(filename)
    body = _norm(text_sample[:8000])
    head = body[:800]
    types = load_document_types().get("types", [])
    best: DocumentType = "unknown"
    best_score = 0.0
    for spec in types:
        doc_id = spec.get("id", "unknown")
        if doc_id == "unknown":
            continue
        score = 0.0
        for kw in spec.get("keywords", []):
            needle = _norm(kw)
            if not needle:
                continue
            if needle in filename_n:
                score += 3.0
            if needle in head:
                score += 2.0
            elif needle in body:
                score += 0.4
        if score > best_score:
            best_score = score
            best = doc_id
    if best_score <= 0:
        return "unknown", 0.0
    confidence = min(1.0, 0.35 + 0.12 * best_score)
    return best, confidence
