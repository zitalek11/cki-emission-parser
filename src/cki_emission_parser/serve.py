from __future__ import annotations

import html
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cki_emission_parser.env import load_local_env
from cki_emission_parser.extraction.instrument import guess_instrument_class
from cki_emission_parser.extraction.llm import LlmRequestError, NullLlmProvider, provider_from_env
from cki_emission_parser.extraction.pipeline import extract_job
from cki_emission_parser.ingestion import ingest_pack
from cki_emission_parser.output.html_review import render_review_html
from cki_emission_parser.paths import package_root

_HOST_DEFAULT = "127.0.0.1"
_PORT_DEFAULT = 8765
_MAX_UPLOAD_BYTES = 40 * 1024 * 1024


def benchmark_root() -> Path:
    return package_root().parent / "_benchmark_artifacts" / "Артефакты для справочника выпусков"


def local_packs() -> list[tuple[str, Path]]:
    root = benchmark_root()
    if not root.is_dir():
        return []
    packs: list[tuple[str, Path]] = []
    for folder in sorted(path for path in root.rglob("*") if path.is_dir()):
        files = [
            item
            for item in folder.iterdir()
            if item.is_file() and item.suffix.lower() in {".pdf", ".docx"}
        ]
        if not files:
            continue
        if any(item.is_dir() for item in folder.iterdir()):
            continue
        label = str(folder.relative_to(root))
        packs.append((label, folder))
    return packs


def extract_to_html(path: Path) -> str:
    job = ingest_pack(path)
    job.instrument_class = guess_instrument_class(job)
    provider = provider_from_env() or NullLlmProvider()
    try:
        report = extract_job(job, provider=provider, instrument_class=job.instrument_class)
    except LlmRequestError as exc:
        return (
            "<!DOCTYPE html><html lang=\"ru\"><meta charset=\"utf-8\"/>"
            f"<body><h1>Ошибка модели</h1><pre>{html.escape(str(exc))}</pre>"
            '<p><a href="/">← новый файл</a></p></body></html>'
        )
    page = render_review_html(report)
    nav = (
        '<p><a href="/">← новый файл</a></p>'
        f"<p class=\"meta\">Источник: {html.escape(str(path))} · "
        f"документов: {len(job.documents)} · класс: "
        f"<code>{html.escape(job.instrument_class)}</code></p>"
    )
    return page.replace("<h1>", nav + "<h1>", 1)


def index_html() -> str:
    llm = provider_from_env() is not None
    llm_line = (
        "Модель подключена."
        if llm
        else "Ключ модели не задан (CKI_LLM_API_KEY / OPENAI_API_KEY). "
        "Будут заполнены только поля с правилом в коде (например валюта)."
    )
    options = "\n".join(
        f'<option value="{html.escape(str(path))}">{html.escape(label)}</option>'
        for label, path in local_packs()
    )
    packs_block = (
        f"<label>Или локальный эталонный комплект<br/><select name=\"pack\">"
        f"<option value=\"\">— не выбран —</option>\n{options}</select></label>"
        if options
        else "<p>Локальные эталонные комплекты не найдены.</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<title>Парсер эмиссионных документов</title>
<style>
body {{ font-family: "Segoe UI", Tahoma, sans-serif; margin: 40px auto; max-width: 720px; }}
label, button {{ display: block; margin: 16px 0; }}
.note {{ background: #f4f7fb; padding: 12px 16px; border-radius: 8px; }}
</style>
</head>
<body>
<h1>Локальный разбор выпуска</h1>
<p class="note">{html.escape(llm_line)}</p>
<p>PDF или DOCX. Нет доказательства → нет значения.</p>
<form method="post" action="/extract" enctype="multipart/form-data">
<label>Файл<br/><input type="file" name="file" accept=".pdf,.docx"/></label>
{packs_block}
<button type="submit">Извлечь</button>
</form>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            return self._send(200, index_html())
        if parsed.path == "/health":
            return self._send(200, "ok", content_type="text/plain; charset=utf-8")
        if parsed.path == "/run":
            query = parse_qs(parsed.query)
            pack = (query.get("pack") or [""])[0]
            return self._extract_pack(pack)
        self._send(404, "Не найдено", content_type="text/plain; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/extract":
            return self._send(404, "Не найдено", content_type="text/plain; charset=utf-8")
        length = int(self.headers.get("Content-Length") or 0)
        if length > _MAX_UPLOAD_BYTES:
            return self._send(413, "Файл слишком большой", content_type="text/plain; charset=utf-8")
        body = self.rfile.read(length) if length else b""
        ctype = self.headers.get("Content-Type", "")
        form = _parse_multipart(ctype, body)
        pack = (form.get("pack") or [""])[0].strip()
        if pack:
            return self._extract_pack(pack)
        upload = form.get("file")
        if not upload or not upload[0]:
            return self._send(400, "Укажите файл или комплект", content_type="text/plain; charset=utf-8")
        filename, payload = upload[0] if isinstance(upload[0], tuple) else ("upload.pdf", upload[0])
        suffix = Path(filename).suffix.lower() or ".pdf"
        if suffix not in {".pdf", ".docx"}:
            return self._send(400, "Нужен PDF или DOCX", content_type="text/plain; charset=utf-8")
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        try:
            return self._send(200, extract_to_html(temp_path))
        except Exception as exc:  # noqa: BLE001
            return self._send(500, f"Ошибка разбора: {exc}", content_type="text/plain; charset=utf-8")
        finally:
            temp_path.unlink(missing_ok=True)

    def _extract_pack(self, pack: str) -> None:
        path = Path(pack)
        root = benchmark_root().resolve()
        try:
            resolved = path.resolve()
        except OSError:
            return self._send(400, "Некорректный путь", content_type="text/plain; charset=utf-8")
        allowed = [item.resolve() for _, item in local_packs()]
        if resolved not in allowed and root not in resolved.parents:
            return self._send(403, "Путь вне эталонных комплектов", content_type="text/plain; charset=utf-8")
        if not resolved.exists():
            return self._send(404, "Комплект не найден", content_type="text/plain; charset=utf-8")
        try:
            self._send(200, extract_to_html(resolved))
        except Exception as exc:  # noqa: BLE001
            self._send(500, f"Ошибка разбора: {exc}", content_type="text/plain; charset=utf-8")

    def _send(self, code: int, body: str, *, content_type: str = "text/html; charset=utf-8") -> None:
        payload = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("%s - %s\n" % (self.address_string(), format % args))


def _parse_multipart(content_type: str, body: bytes) -> dict[str, list]:
    if "multipart/form-data" not in content_type:
        return {}
    boundary = ""
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("=", 1)[1].strip().strip('"')
    if not boundary:
        return {}
    marker = b"--" + boundary.encode("utf-8")
    result: dict[str, list] = {}
    for chunk in body.split(marker):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        header_blob, _, data = chunk.partition(b"\r\n\r\n")
        headers = header_blob.decode("utf-8", errors="replace")
        if data.endswith(b"\r\n"):
            data = data[:-2]
        name = _header_param(headers, "name")
        if not name:
            continue
        filename = _header_param(headers, "filename")
        if filename:
            result.setdefault(name, []).append((filename, data))
        else:
            result.setdefault(name, []).append(data.decode("utf-8", errors="replace"))
    return result


def _header_param(headers: str, key: str) -> str | None:
    for line in headers.split("\r\n"):
        if line.lower().startswith("content-disposition:"):
            for piece in line.split(";"):
                piece = piece.strip()
                if piece.startswith(f"{key}="):
                    return piece.split("=", 1)[1].strip().strip('"')
    return None


def run_server(host: str = _HOST_DEFAULT, port: int = _PORT_DEFAULT) -> None:
    load_local_env()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Локальный разбор: http://{host}:{port}/")
    if provider_from_env() is None:
        print("LLM не задан — поля без правила в коде останутся not_found.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлен.")
        server.server_close()
