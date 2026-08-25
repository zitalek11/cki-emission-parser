from __future__ import annotations

import re

_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^\wа-яё]+", re.IGNORECASE)
_NEGATION = (
    "не являются",
    "не является",
    "не предназначен",
    "не предназначены",
)


def normalize_match_text(text: str) -> str:
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = _WS.sub(" ", text).strip().casefold()
    return text


def quote_in_text(quote: str, text: str, *, min_length: int = 4) -> bool:
    q = normalize_match_text(quote)
    t = normalize_match_text(text)
    if len(q) < min_length:
        return False
    return q in t


def value_supported_by_quote(value: object, quote: str, fragment_text: str) -> bool:
    if value is None:
        return False
    quote_norm = normalize_match_text(quote)
    if not quote_norm:
        return False
    blob = f"{quote_norm} {normalize_match_text(fragment_text)}"
    if isinstance(value, bool):
        negated = _has_negation(quote_norm)
        return (not negated) if value else negated

    raw = normalize_match_text(_value_as_search_text(value))
    if not raw:
        return False
    if raw in blob:
        return True
    digits = re.sub(r"\D+", "", _value_as_search_text(value))
    if len(digits) >= 3 and digits in re.sub(r"\D+", "", quote + fragment_text):
        return True
    tokens = [tok for tok in _NON_ALNUM.split(raw) if len(tok) >= 4]
    if tokens and all(tok in blob for tok in tokens[:3]):
        return True
    return False


def _has_negation(text: str) -> bool:
    return any(normalize_match_text(token) in text for token in _NEGATION)


def _value_as_search_text(value: object) -> str:
    if isinstance(value, bool):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return str(value)
