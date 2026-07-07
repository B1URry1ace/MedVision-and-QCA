"""Пути приложения.

Единственный источник правды для всех модулей.
Совместим с оригинальным src.core.app_paths товарища —
annotator импортирует отсюда через алиас.
"""
from __future__ import annotations

from pathlib import Path


def app_root() -> Path:
    """Корень проекта (папка, где лежит main.py)."""
    return Path(__file__).resolve().parent.parent.parent


def projects_dir() -> Path:
    """Папка с проектами разметчика."""
    d = app_root() / "projects"
    d.mkdir(exist_ok=True)
    return d


def models_dir() -> Path:
    """Папка с .pt файлами моделей."""
    d = app_root() / "models"
    d.mkdir(exist_ok=True)
    return d
