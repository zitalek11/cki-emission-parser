"""Пакет извлечения параметров выпуска из эмиссионной документации."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cki-emission-parser")
except PackageNotFoundError:
    __version__ = "0.1.0"
