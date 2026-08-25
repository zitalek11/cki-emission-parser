from __future__ import annotations

from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    env = Path(__file__).resolve().parents[2] / "config"
    if env.exists():
        return env
    return Path(__file__).resolve().parent / "data"


def prompts_dir() -> Path:
    root = package_root() / "prompts"
    if root.exists():
        return root
    return Path(__file__).resolve().parent / "prompts"
