from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cki_emission_parser.env import load_local_env
from cki_emission_parser.eval.score import load_gold, score_report
from cki_emission_parser.extraction.instrument import guess_instrument_class
from cki_emission_parser.extraction.llm import NullLlmProvider, provider_from_env
from cki_emission_parser.extraction.pipeline import extract_job
from cki_emission_parser.extraction.retrieve import retrieve_job
from cki_emission_parser.ingestion import ingest_pack
from cki_emission_parser.output import (
    infer_output_format,
    job_to_dict,
    report_from_dict,
    report_to_dict,
    retrieval_to_dict,
    write_extract_output,
    write_json,
    write_parse_report,
)
from cki_emission_parser.schema import load_extract_set, load_nrd_catalog

_INSTRUMENTS = (
    "share_common",
    "share_pref",
    "bond_exchange",
    "bond_structured",
    "unknown",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Разбор и извлечение параметров выпуска из эмиссионных документов."
    )
    parser.add_argument("path", type=Path, nargs="?", help="Файл или каталог комплекта")
    parser.add_argument(
        "--out",
        type=Path,
        help="Куда записать отчёт: .json, .xlsx или .html (по расширению)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("json", "xlsx", "html"),
        help="Формат отчёта извлечения, если расширение неоднозначно",
    )
    parser.add_argument(
        "--with-retrieval",
        action="store_true",
        help="Включить retrieval в JSON извлечения (по умолчанию нет)",
    )
    parser.add_argument("--schema-stats", action="store_true", help="Показать размеры схемы и выйти")
    parser.add_argument("--extract", action="store_true", help="Извлечь поля MVP (нужен LLM-ключ)")
    parser.add_argument(
        "--dry-retrieve",
        action="store_true",
        help="Только поиск кандидатов, без вызова модели",
    )
    parser.add_argument("--instrument", choices=_INSTRUMENTS, help="Класс инструмента (иначе по тексту)")
    parser.add_argument(
        "--evaluate",
        type=Path,
        help="YAML эталона: accepted / must-be-empty / known-bad",
    )
    parser.add_argument(
        "--report",
        dest="report_path",
        type=Path,
        help="JSON извлечения для --evaluate",
    )
    parser.add_argument("--serve", action="store_true", help="Локальный HTTP-разбор файлов")
    parser.add_argument("--host", default="127.0.0.1", help="Адрес для --serve")
    parser.add_argument("--port", type=int, default=8765, help="Порт для --serve")
    args = parser.parse_args(argv)
    load_local_env()

    if args.schema_stats:
        catalog = load_nrd_catalog()
        extract = load_extract_set()
        print(f"Каталог НРД: {len(catalog.fields)} полей")
        print(f"Набор извлечения MVP: {len(extract.fields)} полей")
        return 0

    if args.serve:
        from cki_emission_parser.serve import run_server

        run_server(args.host, args.port)
        return 0

    if args.evaluate and args.report_path and not args.path:
        return _evaluate_report(args.report_path, args.evaluate)

    if not args.path:
        print("Укажите файл или каталог комплекта", file=sys.stderr)
        return 2
    if not args.path.exists():
        print(f"Путь не найден: {args.path}", file=sys.stderr)
        return 2

    job = ingest_pack(args.path)
    job.instrument_class = args.instrument or guess_instrument_class(job)
    do_extract = args.extract or bool(args.evaluate)

    if args.dry_retrieve and not do_extract:
        resolved, retrieval = retrieve_job(job, instrument_class=job.instrument_class)
        job.instrument_class = resolved
        payload = retrieval_to_dict(job.job_id, resolved, retrieval)
        return _emit(payload, args.out)

    if do_extract:
        provider = provider_from_env()
        if provider is None:
            print(
                "LLM не задан (CKI_LLM_API_KEY / OPENAI_API_KEY). "
                "Поля останутся not_found. Для проверки поиска: --dry-retrieve.",
                file=sys.stderr,
            )
            provider = NullLlmProvider()
        report = extract_job(job, provider=provider, instrument_class=job.instrument_class)
        payload = report_to_dict(report, include_retrieval=args.with_retrieval)
        if args.out:
            fmt = infer_output_format(args.out, args.output_format)
            write_extract_output(
                report,
                args.out,
                fmt=fmt,
                include_retrieval=args.with_retrieval,
            )
            print(f"Записано: {args.out} ({fmt})")
            if args.evaluate:
                return _print_score(report, args.evaluate, pack_path=str(args.path))
            return 0
        if args.output_format in {"xlsx", "html"}:
            print("Для Excel или HTML укажите --out", file=sys.stderr)
            return 2
        if args.evaluate:
            return _print_score(report, args.evaluate, pack_path=str(args.path))
        summary = {
            "job_id": payload["job_id"],
            "instrument_class": payload["instrument_class"],
            "llm_used": payload["llm_used"],
            "status_counts": payload["status_counts"],
            "review_queue": payload["review_queue"],
            "fields": [
                {
                    "field": item["field"],
                    "status": item["status"],
                    "raw_value": item["raw_value"],
                    "reason": item["reason"],
                }
                for item in payload["fields"]
            ],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    payload = job_to_dict(job, include_fragments=False)
    if args.out:
        write_parse_report(job, args.out, include_fragments=True)
        print(f"Записано: {args.out}")
        return 0

    summary = {
        "job_id": payload["job_id"],
        "instrument_class": job.instrument_class,
        "documents": [
            {
                "filename": doc["filename"],
                "document_type": doc["document_type"],
                "page_count": doc["page_count"],
                "fragment_count": doc["fragment_count"],
                "pages_needing_ocr": doc["pages_needing_ocr"],
            }
            for doc in payload["documents"]
        ],
        "fragment_count": payload["fragment_count"],
        "unknown_document_types": payload["unknown_document_types"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _evaluate_report(report_path: Path, gold_path: Path) -> int:
    payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
    report = report_from_dict(payload)
    return _print_score(report, gold_path)


def _print_score(report, gold_path: Path, *, pack_path: str | None = None) -> int:
    score = score_report(report, load_gold(gold_path), pack_path=pack_path)
    print(json.dumps(score, ensure_ascii=False, indent=2, default=str))
    return 0


def _emit(payload: dict, out: Path | None) -> int:
    if out:
        write_json(payload, out)
        print(f"Записано: {out}")
        return 0
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
