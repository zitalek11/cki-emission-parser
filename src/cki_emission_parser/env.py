from __future__ import annotations

import os
from pathlib import Path

from cki_emission_parser.paths import package_root


def load_local_env() -> None:
    """Подхватывает .env из каталога пакета и корня CKI, не перезаписывая уже заданные переменные."""
    for path in (package_root() / ".env", package_root().parent / ".env"):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value
    if not os.environ.get("CKI_LLM_API_KEY") and os.environ.get("OPENROUTER_API_KEY"):
        os.environ["CKI_LLM_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
