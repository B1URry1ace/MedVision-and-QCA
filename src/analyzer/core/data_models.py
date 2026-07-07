from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class VesselMetrics:
    """QCA-метрики одного сосуда на одном изображении."""
    image_path: str = ""
    image_name: str = ""
    class_id: int = 0
    class_name: str = ""
    quality_ok: bool = True
    laplacian_var: float = 0.0
    mask_area_px: int = 0
    skeleton_length_px: float = 0.0
    vessel_length_mm: float = 0.0
    diameter_min_px: float = 0.0
    diameter_max_px: float = 0.0
    diameter_mean_px: float = 0.0
    diameter_ref_px: float = 0.0
    diameter_stenosis_px: float = 0.0
    stenosis_percent: float = 0.0
    tortuosity: float = 1.0
    proximal_diameter_px: float = 0.0
    distal_diameter_px: float = 0.0

    def stenosis_grade(self) -> str:
        s = self.stenosis_percent
        if s < 25:  return "Норма (<25%)"
        if s < 50:  return "Мягкий (25–50%)"
        if s < 70:  return "Умеренный (50–70%)"
        if s < 90:  return "Тяжёлый (70–90%)"
        return "Критический (≥90%)"


@dataclass
class ImageResult:
    """Все результаты анализа для одного изображения."""
    path: str
    name: str
    loaded: bool = False
    skipped_quality: bool = False
    laplacian_var: float = 0.0
    original: Optional[np.ndarray] = field(default=None, repr=False)
    preprocessed: Optional[np.ndarray] = field(default=None, repr=False)
    overlay: Optional[np.ndarray] = field(default=None, repr=False)
    masks: dict[int, np.ndarray] = field(default_factory=dict, repr=False)
    skeletons: dict[int, np.ndarray] = field(default_factory=dict, repr=False)
    metrics: list[VesselMetrics] = field(default_factory=list)
    error: str = ""