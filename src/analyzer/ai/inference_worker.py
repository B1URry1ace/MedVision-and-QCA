from __future__ import annotations
import os
import traceback
from typing import List

import cv2
import numpy as np
from skimage.morphology import skeletonize

from PySide6.QtCore import QThread, QObject, Signal, Slot

from src.analyzer.core.data_models import ImageResult, VesselMetrics
from src.analyzer.core.preprocessing import (
    ensure_bgr, compute_laplacian_variance, apply_preprocessing,
)
from src.analyzer.core.vessel_analysis import compute_vessel_metrics, build_overlay
from src.shared.constants import SUPPORTED_IMAGE_EXTENSIONS


class InferenceWorkerSignals(QObject):
    progress = Signal(int, int, str)   # current, total, filename
    result   = Signal(object)          # ImageResult
    finished = Signal()
    error    = Signal(str)


class InferenceWorker(QThread):
    """Фоновый поток: пакетный YOLO-инференс + QCA-метрики."""

    def __init__(self, image_paths: List[str], model_path: str,
                 preproc_params: dict, quality_threshold: float,
                 scale_mm_per_px: float) -> None:
        super().__init__()
        self.image_paths      = image_paths
        self.model_path       = model_path
        self.preproc_params   = preproc_params
        self.quality_threshold = quality_threshold
        self.scale_mm_per_px  = scale_mm_per_px
        self.signals          = InferenceWorkerSignals()
        self._cancel          = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            try:
                from ultralytics import YOLO
                model = YOLO(self.model_path)
            except Exception as e:
                self.signals.error.emit(
                    f"Не удалось загрузить модель YOLO:\n{e}\n\n"
                    "Убедитесь что ultralytics установлен и путь к .pt корректный."
                )
                return

            total = len(self.image_paths)
            for i, path in enumerate(self.image_paths):
                if self._cancel:
                    break

                name = os.path.basename(path)
                self.signals.progress.emit(i + 1, total, name)

                res = ImageResult(path=path, name=name)

                img = cv2.imread(path)
                if img is None:
                    res.error = "Не удалось загрузить изображение"
                    self.signals.result.emit(res)
                    continue

                res.loaded   = True
                res.original = ensure_bgr(img)

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                res.laplacian_var = compute_laplacian_variance(gray)

                if res.laplacian_var < self.quality_threshold:
                    res.skipped_quality = True
                    self.signals.result.emit(res)
                    continue

                # Предобработка
                proc = apply_preprocessing(res.original, self.preproc_params)
                res.preprocessed = proc

                # YOLO инференс
                yolo_results = model.predict(proc, verbose=False)
                for r in yolo_results:
                    if r.masks is None:
                        continue
                    for mask_data, cls_tensor in zip(r.masks.data, r.boxes.cls):
                        cls_id   = int(cls_tensor.item())
                        mask_np  = mask_data.cpu().numpy()
                        mask_rsz = cv2.resize(
                            mask_np.astype(np.float32),
                            (proc.shape[1], proc.shape[0])
                        )
                        mask_bin = (mask_rsz > 0.5).astype(np.uint8) * 255
                        if cls_id in res.masks:
                            res.masks[cls_id] = cv2.bitwise_or(res.masks[cls_id], mask_bin)
                        else:
                            res.masks[cls_id] = mask_bin

                # Скелетонизация + метрики
                for cls_id, mask_bin in res.masks.items():
                    skel = skeletonize((mask_bin > 0))
                    res.skeletons[cls_id] = skel.astype(np.uint8) * 255

                    m = compute_vessel_metrics(
                        mask_bin, cls_id, res.name, res.path, self.scale_mm_per_px
                    )
                    m.laplacian_var = res.laplacian_var
                    m.quality_ok    = True
                    res.metrics.append(m)

                res.overlay = build_overlay(proc, res.masks, res.skeletons)
                self.signals.result.emit(res)

        except Exception:
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()