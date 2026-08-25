from __future__ import annotations

import re

from cki_emission_parser.models.schema import FieldSpec
from cki_emission_parser.models.types import FieldResult, SourceFragment
from cki_emission_parser.normalize.dates import looks_like_date_rule

_URL = re.compile(
    r"https?://|www\.|e-disclosure|disclosure\.|\.html|\.php\?|/[a-z0-9_\-]+\.pdf",
    re.IGNORECASE,
)
_OTHER_PARTY = re.compile(
    r"приобретател|покупател|регистратор|депозитар|держател[ьяе]\s+реестра",
    re.IGNORECASE,
)
_ISSUER = re.compile(r"эмитент", re.IGNORECASE)
_SHORT_HINT = re.compile(
    r"сокращ[её]нн|кратк(?:ое|ая|ие)\s+(?:фирменн|наименован)",
    re.IGNORECASE,
)
_FULL_PREFIX = re.compile(
    r"^(?:публичное|открытое|закрытое)\s+акционерное|общество\s+с\s+ограниченной",
    re.IGNORECASE,
)
_FACT = re.compile(r"фактическ\w*\s+размещ", re.IGNORECASE)
_PLAN = re.compile(
    r"размещаем\w*|подлежа\w*\s+размещен|количество\s+ценных\s+бумаг\s+дополнительного",
    re.IGNORECASE,
)
_CFI = re.compile(r"\bcfi\b|код\s+cfi", re.IGNORECASE)
_PLANNED_FIELDS = {"share.issue_size_planned", "bond.issue_size_planned"}
_FACT_FIELDS = {"share.issued_size"}


def apply_validation(
    spec: FieldSpec,
    result: FieldResult,
    fragments: list[SourceFragment],
) -> FieldResult:
    if result.status not in {"confirmed", "derived", "ambiguous"}:
        return result
    quote = result.evidence[0].quote if result.evidence else ""
    blob = quote + "\n" + "\n".join(fragment.text for fragment in fragments)
    reason = _reason(spec, result, quote, blob)
    if reason:
        return FieldResult(
            field=spec.id,
            status="not_found",
            reason=reason,
            review_decision="rejected",
        )
    return result


def _reason(spec: FieldSpec, result: FieldResult, quote: str, blob: str) -> str | None:
    field_id = spec.id
    value = result.normalized_value if result.normalized_value is not None else result.raw_value

    if field_id.endswith(".inn"):
        digits = re.sub(r"\D+", "", str(value or ""))
        if _inn_only_in_url(digits, blob):
            return "ИНН из URL страницы раскрытия не принимается"
        if _URL.search(quote) and "инн" not in quote.casefold():
            return "ИНН из URL страницы раскрытия не принимается"

    if field_id == "cfi":
        if not _CFI.search(quote):
            return "CFI не выводится из признаков бумаги: в цитате нет кода CFI"
        text = str(value or "")
        if not re.fullmatch(r"[A-Za-z]{6}", text):
            return "значение CFI должно состоять из 6 латинских букв"

    if field_id == "issuer.name_short":
        if not _SHORT_HINT.search(quote):
            return "краткое имя не выводится из полного: в цитате нет краткой формы"
        if isinstance(value, str) and _FULL_PREFIX.search(value.strip()):
            return "краткое имя не выводится из полного наименования"

    if field_id.endswith(".ogrn"):
        if _OTHER_PARTY.search(quote) and not _ISSUER.search(quote):
            return "ОГРН принадлежит другой стороне сделки, не эмитенту"

    if field_id in _PLANNED_FIELDS and _FACT.search(quote) and not _PLAN.search(quote):
        return "фактический объём нельзя записывать в плановое поле"
    if field_id in _FACT_FIELDS and _PLAN.search(quote) and not _FACT.search(quote):
        return "плановый объём нельзя записывать в фактическое поле"

    if spec.type == "date":
        normalized = result.normalized_value
        if looks_like_date_rule(quote) and isinstance(normalized, dict):
            if normalized.get("date_kind") != "rule" or normalized.get("normalized"):
                return "правило даты нельзя сводить к календарной дате"

    if spec.type == "boolean" and value is False and not _has_negation(quote):
        return "молчание или цитата без отрицания не равны false"

    return None


def _inn_only_in_url(digits: str, text: str) -> bool:
    if not digits or digits not in text:
        return False
    if re.search(rf"ИНН\s*[:№]?\s*{digits}", text, flags=re.IGNORECASE):
        return False
    hits = 0
    url_hits = 0
    for match in re.finditer(re.escape(digits), text):
        hits += 1
        window = text[max(0, match.start() - 60) : min(len(text), match.end() + 40)]
        if _URL.search(window):
            url_hits += 1
    return hits > 0 and url_hits == hits


def _has_negation(text: str) -> bool:
    folded = text.casefold()
    return any(token in folded for token in ("не являются", "не является", "не предназначен"))
