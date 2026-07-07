from __future__ import annotations
from typing import Optional
import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy


class ImageViewer(QLabel):
    """Просмотр изображения с зумом колесом мыши."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(
            "background-color: #080c10; border: 1px solid #21262d; border-radius: 4px;"
        )
        self._pixmap_orig: Optional[QPixmap] = None
        self._zoom: float = 1.0
        self.setText("Нет изображения")

    def set_image_bgr(self, img_bgr: Optional[np.ndarray]) -> None:
        if img_bgr is None:
            self._pixmap_orig = None
            self.setText("Нет изображения")
            return
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = img_rgb.shape
        qimg = QImage(img_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._pixmap_orig = QPixmap.fromImage(qimg)
        self._update_display()

    def _update_display(self) -> None:
        if self._pixmap_orig is None:
            return
        sz = self.size()
        scaled = self._pixmap_orig.scaled(
            int(sz.width() * self._zoom),
            int(sz.height() * self._zoom),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)

    def resizeEvent(self, e) -> None:
        self._update_display()
        super().resizeEvent(e)

    def wheelEvent(self, e) -> None:
        delta = e.angleDelta().y()
        self._zoom = max(0.2, min(5.0, self._zoom * (1.1 if delta > 0 else 0.9)))
        self._update_display()

    def reset_zoom(self) -> None:
        self._zoom = 1.0
        self._update_display()