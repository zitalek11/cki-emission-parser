from pathlib import Path

from cki_emission_parser.models.schema import ExtractSet
from cki_emission_parser.models.types import ExtractReport
from cki_emission_parser.output.json_dump import (
    job_to_dict,
    report_from_dict,
    report_to_dict,
    retrieval_to_dict,
    write_extract_report,
    write_json,
    write_parse_report,
)
from cki_emission_parser.output.review import review_queue

__all__ = [
    "infer_output_format",
    "job_to_dict",
    "report_from_dict",
    "report_to_dict",
    "retrieval_to_dict",
    "review_queue",
    "write_extract_output",
    "write_extract_report",
    "write_json",
    "write_parse_report",
]


def infer_output_format(path: Path, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    suffix = Path(path).suffix.lower()
    if suffix == ".xlsx":
        return "xlsx"
    if suffix in {".html", ".htm"}:
        return "html"
    return "json"


def write_extract_output(
    report: ExtractReport,
    path: Path,
    *,
    fmt: str | None = None,
    include_retrieval: bool = False,
    extract_set: ExtractSet | None = None,
) -> str:
    fmt = infer_output_format(path, fmt)
    path = Path(path)
    if fmt == "xlsx":
        from cki_emission_parser.output.excel import write_extract_excel

        write_extract_excel(report, path, extract_set=extract_set)
    elif fmt == "html":
        from cki_emission_parser.output.html_review import write_review_html

        write_review_html(report, path, extract_set=extract_set)
    elif fmt == "json":
        write_extract_report(report, path, include_retrieval=include_retrieval)
    else:
        raise ValueError(f"Неизвестный формат отчёта: {fmt}")
    return fmt
