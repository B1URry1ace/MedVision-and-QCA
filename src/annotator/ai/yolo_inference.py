from __future__ import annotations

from pathlib import Path


class YoloInference:
    _cache: dict[str, "YoloInference"] = {}

    def __init__(self, model_path: Path) -> None:
        from ultralytics import YOLO
        self.model_path = model_path
        self.model = YOLO(str(model_path))

    @classmethod
    def get(cls, model_path: Path) -> "YoloInference":
        key = str(model_path.resolve())
        inst = cls._cache.get(key)
        if inst is None:
            inst = cls(model_path)
            cls._cache[key] = inst
        return inst

    def predict(
        self, image_path: str, conf: float = 0.25, device: str | None = None
    ) -> list[list[tuple[float, float]]]:
        kwargs: dict = {"verbose": False, "conf": conf}
        if device is not None:
            kwargs["device"] = device
        results = self.model(image_path, **kwargs)
        polygons: list[list[tuple[float, float]]] = []
        if not results:
            return polygons
        masks = results[0].masks
        if masks is None:
            return polygons
        for poly_xy in masks.xy:
            pts = [(float(x), float(y)) for x, y in poly_xy]
            if len(pts) >= 3:
                polygons.append(pts)
        return polygons


def has_cuda() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False
