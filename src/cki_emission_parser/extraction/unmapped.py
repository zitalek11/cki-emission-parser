from __future__ import annotations

import re

from cki_emission_parser.extraction.quote import normalize_match_text
from cki_emission_parser.extraction.retrieve import iter_fragments
from cki_emission_parser.models.schema import ExtractSet, FieldSpec
from cki_emission_parser.models.types import Evidence, IssueJob, UnmappedFact

_PAIR = re.compile(r"^(.{4,80}?)\s*[:—–]\s*(.+)$")
_SKIP_LABELS = (
    "решение о выпуске",
    "программа облигаций",
    "условия размещения",
    "содержание",
    "оглавление",
    "раздел",
    "глава",
    "приложение",
    "страница",
    "таблица",
)


def collect_unmapped_facts(job: IssueJob, extract_set: ExtractSet) -> list[UnmappedFact]:
    known = _known_labels(extract_set.fields)
    facts: list[UnmappedFact] = []
    seen: set[tuple[str, str]] = set()
    for fragment in iter_fragments(job):
        for raw_line in fragment.text.splitlines():
            line = raw_line.strip()
            match = _PAIR.match(line)
            if match is None:
                continue
            label, value = match.group(1).strip(), match.group(2).strip(" .;")
            if not _looks_like_parameter(label, value):
                continue
            label_key = normalize_match_text(label)
            if _is_known(label_key, known) or _is_skipped(label_key):
                continue
            identity = (label_key, normalize_match_text(value)[:80])
            if identity in seen:
                continue
            seen.add(identity)
            facts.append(
                UnmappedFact(
                    label=label,
                    value=value[:300],
                    source=Evidence(
                        source_id=fragment.source_id,
                        quote=line[:400],
                        page=fragment.page,
                        section=fragment.section,
                    ),
                    possible_field=_hint_field(label_key, extract_set.fields),
                )
            )
    return facts


def _known_labels(fields: list[FieldSpec]) -> set[str]:
    labels: set[str] = set()
    for field in fields:
        labels.add(normalize_match_text(field.id.replace(".", " ")))
        labels.add(normalize_match_text(field.title))
        for synonym in field.synonyms:
            labels.add(normalize_match_text(synonym))
    return {item for item in labels if item}


def _is_known(label_key: str, known: set[str]) -> bool:
    if label_key in known:
        return True
    for item in known:
        if len(item) >= 12 and (item in label_key or label_key in item):
            return True
    return False


def _looks_like_parameter(label: str, value: str) -> bool:
    if len(value) < 2 or len(value) > 220:
        return False
    if label.isdigit() or value.casefold() in {"далее", "см", "см."}:
        return False
    letters = sum(char.isalpha() for char in label)
    return letters >= 4


def _is_skipped(label_key: str) -> bool:
    return any(token in label_key for token in _SKIP_LABELS)


def _hint_field(label_key: str, fields: list[FieldSpec]) -> str | None:
    """Подсказка для ревью, не назначение значения."""
    hits: list[str] = []
    for field in fields:
        title = normalize_match_text(field.title)
        if title and title in label_key and title != label_key:
            hits.append(field.id)
    if len(hits) == 1:
        return hits[0]
    return None
