from __future__ import annotations

import re

from cki_emission_parser.models.types import DateValue

_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

_RULE = re.compile(
    r"(\d+[-\s]*(?:й|ый|ой|ий)\s+(?:рабочий\s+)?день)"
    r"|(по\s+истечении)"
    r"|(с\s+даты\s+начала\s+размещения)"
    r"|(с\s+даты\s+государственной\s+регистрации)"
    r"|(через\s+\d+\s+(?:день|дня|дней|месяц|месяца|месяцев|год|года|лет))"
    r"|(исчисляется\s+с)",
    re.IGNORECASE,
)
_RANGE = re.compile(
    r"(с\s+\d.+\s+по\s+\d)|(по\s+\d{1,2}\.\d{1,2}\.\d{2,4}\s+включительно)",
    re.IGNORECASE,
)
_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_DOTTED = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b")
_NAMED = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)


def looks_like_date_rule(text: str) -> bool:
    return bool(_RULE.search(text or ""))


def parse_date_value(raw: object, quote: str) -> DateValue:
    quote = quote or ""
    raw_text = quote or str(raw or "").strip()
    if looks_like_date_rule(quote) or looks_like_date_rule(str(raw or "")):
        return DateValue(date_kind="rule", raw_text=raw_text, normalized=None)
    if _RANGE.search(quote):
        return DateValue(date_kind="range", raw_text=raw_text, normalized=None)
    exact = parse_exact_date(quote) or parse_exact_date(str(raw or ""))
    if exact:
        return DateValue(date_kind="exact", raw_text=raw_text, normalized=exact)
    if raw_text:
        return DateValue(date_kind="relative", raw_text=raw_text, normalized=None)
    raise ValueError("нет даты в цитате")


def parse_exact_date(text: str) -> str | None:
    text = (text or "").strip()
    iso = _ISO.match(text)
    if iso:
        return _ymd(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    dotted = _DOTTED.search(text)
    if dotted:
        day, month, year = int(dotted.group(1)), int(dotted.group(2)), int(dotted.group(3))
        if year < 100:
            year += 2000
        return _ymd(year, month, day)
    named = _NAMED.search(text)
    if named:
        day = int(named.group(1))
        month = _MONTHS[named.group(2).casefold()]
        year = int(named.group(3))
        return _ymd(year, month, day)
    return None


def _ymd(year: int, month: int, day: int) -> str | None:
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1990 <= year <= 2100):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"
