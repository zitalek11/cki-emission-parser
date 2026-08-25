#!/usr/bin/env python3
"""Копирует эталонный архив в data/examples/packs/ (файлы в git не входят)."""

from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "examples" / "packs"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="ZIP или уже распакованный каталог")
    args = parser.parse_args()
    source: Path = args.source
    DEST.mkdir(parents=True, exist_ok=True)

    if source.is_file() and source.suffix.lower() == ".zip":
        with zipfile.ZipFile(source) as archive:
            archive.extractall(DEST)
        print(f"Распаковано в {DEST}")
        return 0
    if source.is_dir():
        target = DEST / source.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        print(f"Скопировано в {target}")
        return 0
    print(f"Источник не найден: {source}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
