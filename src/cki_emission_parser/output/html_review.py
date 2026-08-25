from __future__ import annotations

import html
from collections import Counter
from pathlib import Path

from cki_emission_parser.models.schema import ExtractSet, FieldSpec
from cki_emission_parser.models.types import ExtractReport, FieldResult
from cki_emission_parser.output.review import (
    format_display_value,
    needs_review,
    quotes_joined,
    review_label_ru,
    review_queue,
    status_label_ru,
)
from cki_emission_parser.schema import load_extract_set

_STATUS_CLASS = {
    "confirmed": "ok",
    "derived": "derived",
    "ambiguous": "warn",
    "conflict": "bad",
    "not_found": "muted",
    "not_applicable": "muted",
}


def write_review_html(
    report: ExtractReport,
    path: Path,
    *,
    extract_set: ExtractSet | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_review_html(report, extract_set=extract_set), encoding="utf-8")


def render_review_html(
    report: ExtractReport,
    *,
    extract_set: ExtractSet | None = None,
) -> str:
    extract_set = extract_set or load_extract_set()
    specs = {spec.id: spec for spec in extract_set.fields}
    queue = review_queue(report)
    review_fields = [field for field in report.fields if needs_review(field)]
    body = [
        "<!DOCTYPE html>",
        '<html lang="ru">',
        "<head>",
        '<meta charset="utf-8"/>',
        "<title>Ревью извлечения выпуска</title>",
        f"<style>{_CSS}</style>",
        "</head>",
        "<body>",
        "<h1>Ревью извлечения параметров выпуска</h1>",
        "<p class=\"lead\">Источник истины — цитата в документе. Нет доказательства → нет значения.</p>",
        _summary(report, queue),
        "<h2>Поля на проверку</h2>",
    ]
    if not review_fields:
        body.append("<p>Спорных полей нет.</p>")
    else:
        body.extend(_field_card(field, specs.get(field.field)) for field in review_fields)
    body.append("<h2>Несопоставленные факты</h2>")
    if not report.unmapped_facts:
        body.append("<p>Неизвестных параметров не найдено.</p>")
    else:
        body.append("<ul class=\"unmapped\">")
        for fact in report.unmapped_facts:
            hint = f" возможное поле <code>{html.escape(fact.possible_field)}</code>" if fact.possible_field else ""
            body.append(
                "<li><strong>"
                f"{html.escape(fact.label)}</strong>: {html.escape(fact.value)}"
                f"<blockquote>{html.escape(fact.source.quote)}</blockquote>"
                f"<span class=\"meta\">source_id={html.escape(fact.source.source_id)}{hint}</span></li>"
            )
        body.append("</ul>")
    body.append("<h2>Все поля</h2>")
    body.append(_all_fields_table(report.fields, specs))
    body.extend(["</body>", "</html>"])
    return "\n".join(body)


def _summary(report: ExtractReport, queue: dict) -> str:
    counts = queue
    status_bits = []
    for status, count in Counter(field.status for field in report.fields).items():
        status_bits.append(f"{status_label_ru(status)}: {count}")
    return (
        "<section class=\"summary\">"
        f"<p>Задание: <code>{html.escape(report.job_id)}</code>. "
        f"Класс: <code>{html.escape(report.instrument_class)}</code>. "
        f"LLM: {'да' if report.llm_used else 'нет'}.</p>"
        f"<p>{'. '.join(status_bits) or 'Полей нет'}.</p>"
        f"<p>На проверку: {len(counts['field_ids'])}. "
        f"Конфликтов: {counts['conflict_count']}. "
        f"Несопоставленных фактов: {counts['unmapped_count']}.</p>"
        "</section>"
    )


def _field_card(field: FieldResult, spec: FieldSpec | None) -> str:
    title = spec.title if spec else field.field
    css = _STATUS_CLASS.get(field.status, "muted")
    quotes = "".join(
        f"<blockquote>{html.escape(item.quote)}"
        f"<cite>source_id={html.escape(item.source_id)}"
        f"{', стр. ' + str(item.page) if item.page else ''}</cite></blockquote>"
        for item in field.evidence
    ) or "<p class=\"muted\">Цитаты нет.</p>"
    return (
        f"<article class=\"card {css}\">"
        f"<h3>{html.escape(title)} <code>{html.escape(field.field)}</code></h3>"
        f"<p><span class=\"pill {css}\">{html.escape(status_label_ru(field.status))}</span> "
        f"<span class=\"pill\">{html.escape(review_label_ru(field.review_decision))}</span></p>"
        f"<p>Значение: <strong>{html.escape(format_display_value(field.raw_value))}</strong></p>"
        f"<p>Нормализовано: {html.escape(format_display_value(field.normalized_value)) or '—'}</p>"
        f"{quotes}"
        f"<p class=\"reason\">{html.escape(field.reason or '')}</p>"
        "</article>"
    )


def _all_fields_table(fields: list[FieldResult], specs: dict[str, FieldSpec]) -> str:
    rows = [
        "<table><thead><tr>"
        "<th>Поле</th><th>Название</th><th>Статус</th><th>Значение</th><th>Цитата</th>"
        "</tr></thead><tbody>"
    ]
    for field in fields:
        spec = specs.get(field.field)
        title = spec.title if spec else field.field
        css = _STATUS_CLASS.get(field.status, "muted")
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(field.field)}</code></td>"
            f"<td>{html.escape(title)}</td>"
            f"<td><span class=\"pill {css}\">{html.escape(status_label_ru(field.status))}</span></td>"
            f"<td>{html.escape(format_display_value(field.raw_value))}</td>"
            f"<td>{html.escape(quotes_joined(field))}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


_CSS = """
body { font-family: Georgia, "Times New Roman", serif; margin: 24px auto; max-width: 1100px; color: #1a1a1a; }
code { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 0.9em; }
h1, h2, h3 { font-family: "Segoe UI", Tahoma, sans-serif; }
.lead { color: #444; }
.summary { background: #f4f7fb; padding: 12px 16px; border-radius: 8px; }
.card { border: 1px solid #ddd; border-radius: 8px; padding: 12px 16px; margin: 12px 0; }
.card.bad { border-color: #c0392b; background: #fdf2f2; }
.card.warn { border-color: #d68910; background: #fff8e8; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eee; font-size: 0.85em; }
.pill.ok { background: #d5f5e3; }
.pill.derived { background: #d6eaf8; }
.pill.warn { background: #fdebd0; }
.pill.bad { background: #f5b7b1; }
.pill.muted { background: #e5e8e8; }
blockquote { margin: 8px 0; padding: 8px 12px; background: #fff; border-left: 3px solid #1f4e79; }
cite { display: block; color: #666; font-size: 0.85em; margin-top: 4px; }
.meta, .reason { color: #555; font-size: 0.9em; }
table { width: 100%; border-collapse: collapse; font-size: 0.92em; }
th, td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
th { background: #1f4e79; color: #fff; text-align: left; }
"""
