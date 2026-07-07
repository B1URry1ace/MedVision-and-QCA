"""Общие константы для обоих модулей."""
from __future__ import annotations

APP_NAME = "MedVision"
APP_ORG  = "MedVision"

# Классы YOLO-модели анализатора
ANALYZER_CLASS_NAMES: dict[int, str] = {
    0: "Right coronary artery",
    1: "Left coronary artery",
}

# Цвета масок анализатора (R, G, B)
ANALYZER_CLASS_COLORS: dict[int, tuple[int, int, int]] = {
    0: (255, 80,  80),
    1: (80,  200, 255),
}

SUPPORTED_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
)

ANALYZER_QUALITY_THRESHOLD_DEFAULT: float = 100.0
