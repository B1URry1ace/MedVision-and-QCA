from __future__ import annotations

from pathlib import Path


def app_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def projects_dir() -> Path:
    d = app_root() / "projects"
    d.mkdir(exist_ok=True)
    return d
