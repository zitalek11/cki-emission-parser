from __future__ import annotations

import re
from datetime import date, datetime
from functools import lru_cache

from cki_emission_parser.models.schema import FieldSpec
from cki_emission_parser.models.types import MoneyValue
from cki_emission_parser.normalize.dates import parse_date_value
from cki_emission_parser.schema import load_normalization

_SPACES = re.compile(r"[\s\u00a0\u202f]+")
_FIRST_INT = re.compile(r"\d[\d\s\u00a0\u202f]*")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


class CannotNormalize(ValueError):
    pass


def normalize_value(spec: FieldSpec, raw: object, quote: str) -> object:
    kind = spec.type
    if kind == "boolean":
        return _boolean(raw)
    if kind == "integer":
        return _integer(raw)
    if kind == "money":
        return _money(raw, quote)
    if kind == "date":
        return parse_date_value(raw, quote)
    if kind == "currency":
        code = currency_from_text(str(raw or "")) or currency_from_text(quote)
        if not code:
            raise CannotNormalize("не удалось определить код валюты")
        return code
    if spec.id.endswith(".inn"):
        return _inn(raw, quote)
    if spec.id.endswith(".ogrn"):
        return _ogrn(raw, quote)
    if kind in {"string", "enum"}:
        return _string(raw)
    return raw


def currency_from_text(text: str) -> str | None:
    blob = text or ""
    for rule in _currency_rules():
        if re.search(rule["pattern"], blob, flags=re.IGNORECASE):
            return str(rule["code"])
    return None


def currency_match_span(text: str) -> tuple[str, str] | None:
    blob = text or ""
    for rule in _currency_rules():
        match = re.search(rule["pattern"], blob, flags=re.IGNORECASE)
        if match:
            return str(rule["code"]), match.group(0)
    return None


@lru_cache(maxsize=1)
def _currency_rules() -> tuple[dict, ...]:
    raw = load_normalization() or {}
    return tuple(raw.get("currency_from_text") or ())


def _boolean(raw: object) -> bool:
    if isinstance(raw, bool):
        return raw
    text = str(raw or "").strip().casefold()
    if text in {"true", "да", "1"}:
        return True
    if text in {"false", "нет", "0"}:
        return False
    raise CannotNormalize("значение не является булевым")


def _integer(raw: object) -> int:
    if isinstance(raw, bool) or isinstance(raw, (datetime, date)):
        raise CannotNormalize("целое поле не может быть датой или булевым")
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, int):
        return raw
    text = str(raw or "").strip()
    if _ISO_DATE.match(text):
        raise CannotNormalize("целое поле не принимает календарную дату")
    match = _FIRST_INT.search(text)
    if not match:
        raise CannotNormalize("нет цифр для целого значения")
    return int(re.sub(r"\D+", "", match.group(0)))


def _money(raw: object, quote: str) -> MoneyValue:
    if isinstance(raw, MoneyValue):
        currency = raw.currency or currency_from_text(quote)
        return MoneyValue(amount=raw.amount, currency=currency, raw_text=raw.raw_text)
    if isinstance(raw, dict) and "amount" in raw:
        amount = float(raw["amount"])
        currency = raw.get("currency") or currency_from_text(quote)
        return MoneyValue(amount=amount, currency=currency, raw_text=str(raw.get("raw_text") or quote))
    if isinstance(raw, (datetime, date)):
        raise CannotNormalize("денежное поле не может быть датой")
    amount = float(_integer(raw))
    return MoneyValue(amount=amount, currency=currency_from_text(quote), raw_text=quote or str(raw))


def _inn(raw: object, quote: str) -> str:
    digits = _best_digits(raw, quote, allowed={10, 12})
    if digits is None:
        raise CannotNormalize("ИНН должен содержать 10 или 12 цифр")
    return digits


def _ogrn(raw: object, quote: str) -> str:
    digits = _best_digits(raw, quote, allowed={13, 15})
    if digits is None:
        raise CannotNormalize("ОГРН должен содержать 13 или 15 цифр")
    return digits


def _best_digits(raw: object, quote: str, *, allowed: set[int]) -> str | None:
    blob = f"{raw or ''} {quote or ''}"
    candidates = [re.sub(r"\D+", "", item) for item in re.findall(r"[\d\s]+", blob)]
    candidates = [item for item in candidates if len(item) in allowed]
    if not candidates:
        compact = re.sub(r"\D+", "", blob)
        return compact if len(compact) in allowed else None
    candidates.sort(key=len, reverse=True)
    return candidates[0]


def _string(raw: object) -> str:
    text = _SPACES.sub(" ", str(raw or "").strip())
    if not text:
        raise CannotNormalize("пустая строка")
    return text
