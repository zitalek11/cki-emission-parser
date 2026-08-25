from __future__ import annotations

import re

from cki_emission_parser.models.types import InstrumentClass, IssueJob

_BOND = ("облигац", "bond")
_SHARE = ("акци", "share")
_PREF = ("привилегир",)
_HEAD_CHARS = 1500
_NEGATED_STRUCTURED = (
    "не являются структурн",
    "не является структурн",
    "не могут являться структурн",
    "не может являться структурн",
)
_STRUCTURED_SECTION = re.compile(
    r"для структурн\w* облигац\w*",
    flags=re.IGNORECASE,
)


def guess_instrument_class(job: IssueJob) -> InstrumentClass:
    head = _head_text(job)
    sample = head
    bond = sum(sample.count(token) for token in _BOND)
    share = sum(sample.count(token) for token in _SHARE)
    if bond == 0 and share == 0:
        sample = _body_text(job)
        bond = sum(sample.count(token) for token in _BOND)
        share = sum(sample.count(token) for token in _SHARE)
        if bond == 0 and share == 0:
            return "unknown"
    if bond >= share:
        # Только заголовок: в теле часто «не являются структурными».
        if _positive_structured(head):
            return "bond_structured"
        return "bond_exchange"
    if any(token in sample for token in _PREF):
        return "share_pref"
    return "share_common"


def _positive_structured(text: str) -> bool:
    cleaned = text
    for phrase in _NEGATED_STRUCTURED:
        cleaned = cleaned.replace(phrase, " ")
    cleaned = _STRUCTURED_SECTION.sub(" ", cleaned)
    return "структурн" in cleaned


def _head_text(job: IssueJob) -> str:
    parts: list[str] = []
    for document in job.documents:
        parts.append(document.filename.replace("+", " ").replace("_", " ").casefold())
        chars = 0
        chunk: list[str] = []
        for fragment in document.fragments:
            chunk.append(fragment.text)
            chars += len(fragment.text)
            if chars >= _HEAD_CHARS:
                break
        parts.append(" ".join(chunk).casefold())
    return " ".join(parts)


def _body_text(job: IssueJob) -> str:
    parts: list[str] = []
    for document in job.documents:
        parts.append(document.filename.casefold())
        for fragment in document.fragments[:40]:
            parts.append(fragment.text.casefold())
            if sum(len(item) for item in parts) > 12000:
                return " ".join(parts)
    return " ".join(parts)
