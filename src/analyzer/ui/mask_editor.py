"""
Встроенный редактор масок для модуля «Анализ».

Позволяет вручную исправить ошибки сегментации YOLO (кисть, ластик, полигон)
прямо в анализаторе перед расчётом QCA-метрик. Полностью самодостаточен —
не зависит от модуля разметки товарища.

Путь в проекте: src/analyzer/ui/mask_editor.py
"""
from __future__ import annotations
from collections import deque
from typing import Optional

import cv2
import numpy as np

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QPolygon
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from src.shared.constants import ANALYZER_CLASS_NAMES, ANALYZER_CLASS_COLORS


# ─────────────────────────────────────────────────────────────────────────
#  Холст редактирования маски
# ─────────────────────────────────────────────────────────────────────────
class MaskCanvas(QWidget):
    """Холст: рисование/стирание/полигон по бинарным маскам поверх кадра."""

    BRUSH = "brush"
    ERASE = "erase"
    POLY = "polygon"

    changed = Signal()  # маска изменилась

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background:#0b0f14;")

        self._img_rgb: Optional[np.ndarray] = None        # HxWx3 RGB
        self._masks: dict[int, np.ndarray] = {}           # cls -> HxW uint8 {0,255}
        self._cls: int = 0
        self._tool: str = self.BRUSH
        self._brush: int = 14
        self._alpha: float = 0.45
        self._zoom: float = 1.0

        self._painting = False
        self._last_pt: Optional[tuple[int, int]] = None
        self._cursor_pt: Optional[QPoint] = None
        self._poly: list[tuple[int, int]] = []

        self._undo: deque = deque(maxlen=40)
        self._redo: deque = deque(maxlen=40)

        self._comp_arr: Optional[np.ndarray] = None       # кэш скомпонованного RGB
        self._comp_qimg: Optional[QImage] = None
        self._dirty = True

    # ── публичный API ────────────────────────────────────────────────────
    def set_image(self, img_bgr: np.ndarray) -> None:
        self._img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        self._dirty = True
        self.update()

    def set_masks(self, masks: dict[int, np.ndarray]) -> None:
        """Принять КОПИИ масок (редактор не трогает оригинал)."""
        self._masks = {}
        if self._img_rgb is not None:
            h, w = self._img_rgb.shape[:2]
        else:
            h = w = None
        for cls_id, m in masks.items():
            mm = (m > 0).astype(np.uint8) * 255
            if h is not None and mm.shape[:2] != (h, w):
                mm = cv2.resize(mm, (w, h), interpolation=cv2.INTER_NEAREST)
            self._masks[int(cls_id)] = mm
        self._undo.clear(); self._redo.clear()
        self._dirty = True
        self.update()

    def get_masks(self) -> dict[int, np.ndarray]:
        """Вернуть непустые маски (классы без пикселей отбрасываются)."""
        out = {}
        for cls_id, m in self._masks.items():
            if int((m > 0).sum()) > 0:
                out[cls_id] = (m > 0).astype(np.uint8) * 255
        return out

    def set_class(self, cls_id: int) -> None:
        self._cls = int(cls_id); self._dirty = True; self.update()

    def set_tool(self, tool: str) -> None:
        self._tool = tool
        self._poly.clear()
        self.update()

    def set_brush(self, r: int) -> None:
        self._brush = max(1, int(r)); self.update()

    def set_alpha(self, a: float) -> None:
        self._alpha = float(np.clip(a, 0.05, 1.0)); self._dirty = True; self.update()

    def reset_zoom(self) -> None:
        self._zoom = 1.0; self.update()

    # ── геометрия отображения ────────────────────────────────────────────
    def _img_size(self):
        if self._img_rgb is None:
            return 0, 0
        h, w = self._img_rgb.shape[:2]
        return w, h

    def _scale(self) -> float:
        w, h = self._img_size()
        if w == 0:
            return 1.0
        fit = min(self.width() / w, self.height() / h)
        return max(0.01, fit * self._zoom)

    def _offset(self, scale: float):
        w, h = self._img_size()
        dw, dh = w * scale, h * scale
        return (self.width() - dw) / 2.0, (self.height() - dh) / 2.0

    def _to_image(self, wx: float, wy: float):
        scale = self._scale()
        ox, oy = self._offset(scale)
        x = int(round((wx - ox) / scale))
        y = int(round((wy - oy) / scale))
        return x, y

    def _in_bounds(self, x: int, y: int) -> bool:
        w, h = self._img_size()
        return 0 <= x < w and 0 <= y < h

    # ── компоновка изображения с масками ─────────────────────────────────
    def _ensure_mask(self, cls_id: int) -> np.ndarray:
        w, h = self._img_size()
        if cls_id not in self._masks:
            self._masks[cls_id] = np.zeros((h, w), np.uint8)
        return self._masks[cls_id]

    def _composite(self) -> None:
        if self._img_rgb is None:
            return
        out = self._img_rgb.astype(np.float32)
        for cls_id, mask in self._masks.items():
            m = mask > 0
            if not m.any():
                continue
            color = np.array(ANALYZER_CLASS_COLORS.get(cls_id, (200, 200, 200)), np.float32)
            a = self._alpha if cls_id == self._cls else self._alpha * 0.45
            out[m] = out[m] * (1.0 - a) + color * a
            # контур активного класса — ярче
            if cls_id == self._cls:
                cont, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                tmp = out.astype(np.uint8).copy()
                cv2.drawContours(tmp, cont, -1, tuple(int(c) for c in color), 1)
                out = tmp.astype(np.float32)
        self._comp_arr = np.ascontiguousarray(np.clip(out, 0, 255).astype(np.uint8))
        h, w = self._comp_arr.shape[:2]
        self._comp_qimg = QImage(self._comp_arr.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._dirty = False

    # ── отрисовка ────────────────────────────────────────────────────────
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0b0f14"))
        if self._img_rgb is None:
            p.setPen(QColor("#8b949e"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Нет изображения")
            return
        if self._dirty or self._comp_qimg is None:
            self._composite()

        scale = self._scale()
        ox, oy = self._offset(scale)
        w, h = self._img_size()
        target = self._comp_qimg.scaled(
            int(w * scale), int(h * scale),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        p.drawImage(int(ox), int(oy), target)

        # полигон в процессе
        if self._poly:
            pen = QPen(QColor("#f1c40f")); pen.setWidth(2)
            p.setPen(pen)
            qpts = [QPoint(int(ox + x * scale), int(oy + y * scale)) for x, y in self._poly]
            if len(qpts) >= 2:
                p.drawPolyline(QPolygon(qpts))
            for q in qpts:
                p.drawEllipse(q, 3, 3)

        # курсор-кисть
        if self._cursor_pt is not None and self._tool in (self.BRUSH, self.ERASE):
            pen = QPen(QColor("#ffffff") if self._tool == self.BRUSH else QColor("#ff6b6b"))
            pen.setWidth(1)
            p.setPen(pen)
            rr = int(self._brush * scale)
            p.drawEllipse(self._cursor_pt, rr, rr)

    # ── мышь ─────────────────────────────────────────────────────────────
    def mousePressEvent(self, e) -> None:
        if self._img_rgb is None:
            return
        x, y = self._to_image(e.position().x(), e.position().y())
        if e.button() == Qt.MouseButton.LeftButton:
            if self._tool == self.POLY:
                if self._in_bounds(x, y):
                    self._poly.append((x, y))
                    self.update()
            else:
                self._push_undo(self._cls)
                self._painting = True
                self._last_pt = (x, y)
                self._stroke((x, y), (x, y))
        elif e.button() == Qt.MouseButton.RightButton and self._tool == self.POLY:
            self._finish_polygon()

    def mouseMoveEvent(self, e) -> None:
        self._cursor_pt = QPoint(int(e.position().x()), int(e.position().y()))
        if self._painting and self._last_pt is not None:
            x, y = self._to_image(e.position().x(), e.position().y())
            self._stroke(self._last_pt, (x, y))
            self._last_pt = (x, y)
        self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton and self._painting:
            self._painting = False
            self._last_pt = None
            self.changed.emit()

    def mouseDoubleClickEvent(self, e) -> None:
        if self._tool == self.POLY:
            self._finish_polygon()

    def wheelEvent(self, e) -> None:
        self._zoom = float(np.clip(self._zoom * (1.15 if e.angleDelta().y() > 0 else 0.87), 0.2, 8.0))
        self._dirty = True
        self.update()

    def keyPressEvent(self, e) -> None:
        k = e.key()
        if k == Qt.Key.Key_BracketLeft:
            self.set_brush(self._brush - 2)
        elif k == Qt.Key.Key_BracketRight:
            self.set_brush(self._brush + 2)
        elif k == Qt.Key.Key_Return or k == Qt.Key.Key_Enter:
            if self._tool == self.POLY:
                self._finish_polygon()
        elif k == Qt.Key.Key_Escape:
            self._poly.clear(); self.update()
        else:
            super().keyPressEvent(e)

    # ── операции рисования ───────────────────────────────────────────────
    def _stroke(self, p0, p1) -> None:
        mask = self._ensure_mask(self._cls)
        val = 255 if self._tool == self.BRUSH else 0
        cv2.line(mask, p0, p1, val, thickness=self._brush * 2)
        cv2.circle(mask, p1, self._brush, val, -1)
        self._dirty = True
        self.update()

    def _finish_polygon(self) -> None:
        if len(self._poly) >= 3:
            self._push_undo(self._cls)
            mask = self._ensure_mask(self._cls)
            pts = np.array(self._poly, np.int32).reshape((-1, 1, 2))
            val = 0 if self._tool == self.ERASE else 255
            cv2.fillPoly(mask, [pts], val)
            self._dirty = True
            self.changed.emit()
        self._poly.clear()
        self.update()

    def clear_class(self) -> None:
        if self._cls in self._masks and self._masks[self._cls].any():
            self._push_undo(self._cls)
            self._masks[self._cls][:] = 0
            self._dirty = True
            self.changed.emit()
            self.update()

    # ── Undo / Redo ──────────────────────────────────────────────────────
    def _push_undo(self, cls_id: int) -> None:
        cur = self._masks.get(cls_id)
        snap = cur.copy() if cur is not None else None
        self._undo.append((cls_id, snap))
        self._redo.clear()

    def undo(self) -> None:
        if not self._undo:
            return
        cls_id, snap = self._undo.pop()
        cur = self._masks.get(cls_id)
        self._redo.append((cls_id, cur.copy() if cur is not None else None))
        if snap is None:
            self._masks.pop(cls_id, None)
        else:
            self._masks[cls_id] = snap
        self._dirty = True; self.changed.emit(); self.update()

    def redo(self) -> None:
        if not self._redo:
            return
        cls_id, snap = self._redo.pop()
        cur = self._masks.get(cls_id)
        self._undo.append((cls_id, cur.copy() if cur is not None else None))
        if snap is None:
            self._masks.pop(cls_id, None)
        else:
            self._masks[cls_id] = snap
        self._dirty = True; self.changed.emit(); self.update()


# ─────────────────────────────────────────────────────────────────────────
#  Диалог редактора
# ─────────────────────────────────────────────────────────────────────────
class MaskEditorDialog(QDialog):
    """Диалог ручной правки маски YOLO перед расчётом QCA."""

    def __init__(self, img_bgr: np.ndarray, masks: dict[int, np.ndarray],
                 parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ручная правка маски сегментации")
        self.setMinimumSize(1000, 720)
        self.result_masks: dict[int, np.ndarray] = {}

        self.canvas = MaskCanvas()
        self.canvas.set_image(img_bgr)
        self.canvas.set_masks(masks)

        self._build_ui()
        # стартовый класс — первый присутствующий в маске
        if masks:
            first = sorted(masks.keys())[0]
            idx = list(ANALYZER_CLASS_NAMES.keys()).index(first) if first in ANALYZER_CLASS_NAMES else 0
            self.combo_class.setCurrentIndex(idx)
            self.canvas.set_class(first)

    # ── интерфейс ────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Класс:"))
        self.combo_class = QComboBox()
        self._class_ids = list(ANALYZER_CLASS_NAMES.keys())
        self.combo_class.addItems([ANALYZER_CLASS_NAMES[c] for c in self._class_ids])
        self.combo_class.currentIndexChanged.connect(
            lambda i: self.canvas.set_class(self._class_ids[i])
        )
        bar.addWidget(self.combo_class)
        bar.addSpacing(12)

        self.btn_brush = QPushButton("✏ Кисть")
        self.btn_erase = QPushButton("⌫ Ластик")
        self.btn_poly = QPushButton("⬠ Полигон")
        for b in (self.btn_brush, self.btn_erase, self.btn_poly):
            b.setCheckable(True)
            bar.addWidget(b)
        self.btn_brush.setChecked(True)
        self.btn_brush.clicked.connect(lambda: self._set_tool(MaskCanvas.BRUSH))
        self.btn_erase.clicked.connect(lambda: self._set_tool(MaskCanvas.ERASE))
        self.btn_poly.clicked.connect(lambda: self._set_tool(MaskCanvas.POLY))

        bar.addSpacing(12)
        bar.addWidget(QLabel("Размер:"))
        self.spin_brush = QSpinBox()
        self.spin_brush.setRange(1, 120)
        self.spin_brush.setValue(14)
        self.spin_brush.valueChanged.connect(self.canvas.set_brush)
        bar.addWidget(self.spin_brush)

        bar.addWidget(QLabel("Прозрачность:"))
        self.sl_alpha = QSlider(Qt.Orientation.Horizontal)
        self.sl_alpha.setFixedWidth(110)
        self.sl_alpha.setRange(10, 100)
        self.sl_alpha.setValue(45)
        self.sl_alpha.valueChanged.connect(lambda v: self.canvas.set_alpha(v / 100.0))
        bar.addWidget(self.sl_alpha)

        bar.addStretch()
        self.btn_undo = QPushButton("↶ Отмена")
        self.btn_redo = QPushButton("↷ Повтор")
        self.btn_clear = QPushButton("Очистить класс")
        self.btn_zoom = QPushButton("1:1")
        self.btn_undo.clicked.connect(self.canvas.undo)
        self.btn_redo.clicked.connect(self.canvas.redo)
        self.btn_clear.clicked.connect(self.canvas.clear_class)
        self.btn_zoom.clicked.connect(self.canvas.reset_zoom)
        for b in (self.btn_undo, self.btn_redo, self.btn_clear, self.btn_zoom):
            bar.addWidget(b)
        root.addLayout(bar)

        root.addWidget(self.canvas, 1)

        hint = QLabel(
            "ЛКМ — рисовать • колесо — зум • Полигон: ЛКМ — точки, "
            "двойной клик / ПКМ / Enter — замкнуть, Esc — отменить • "
            "[ ] — размер кисти • Ctrl+Z / Ctrl+Y — отмена/повтор"
        )
        hint.setStyleSheet("color:#8b949e; font-size:11px;")
        root.addWidget(hint)

        bottom = QHBoxLayout()
        self.btn_save = QPushButton("💾 Сохранить маску (PNG)…")
        self.btn_save.clicked.connect(self._save_png)
        bottom.addWidget(self.btn_save)
        bottom.addStretch()
        self.btn_apply = QPushButton("✓ Применить и пересчитать")
        self.btn_apply.setDefault(True)
        self.btn_cancel = QPushButton("Отмена")
        self.btn_apply.clicked.connect(self._apply)
        self.btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(self.btn_cancel)
        bottom.addWidget(self.btn_apply)
        root.addLayout(bottom)

    def _set_tool(self, tool: str) -> None:
        self.btn_brush.setChecked(tool == MaskCanvas.BRUSH)
        self.btn_erase.setChecked(tool == MaskCanvas.ERASE)
        self.btn_poly.setChecked(tool == MaskCanvas.POLY)
        self.canvas.set_tool(tool)

    # ── горячие клавиши Undo/Redo на уровне диалога ──────────────────────
    def keyPressEvent(self, e) -> None:
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if e.key() == Qt.Key.Key_Z:
                self.canvas.undo(); return
            if e.key() == Qt.Key.Key_Y:
                self.canvas.redo(); return
        super().keyPressEvent(e)

    # ── действия ─────────────────────────────────────────────────────────
    def _save_png(self) -> None:
        masks = self.canvas.get_masks()
        if not masks:
            QMessageBox.information(self, "Пусто", "Маска пуста — нечего сохранять.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить маску активного класса", "mask.png", "PNG (*.png)"
        )
        if not path:
            return
        cls = self._class_ids[self.combo_class.currentIndex()]
        m = masks.get(cls)
        if m is None:
            QMessageBox.information(self, "Пусто",
                                    "У активного класса нет маски.")
            return
        cv2.imwrite(path, m)
        QMessageBox.information(self, "Готово", f"Маска сохранена:\n{path}")

    def _apply(self) -> None:
        self.result_masks = self.canvas.get_masks()
        if not self.result_masks:
            r = QMessageBox.question(
                self, "Пустая маска",
                "Все маски пусты. Применить (метрики будут очищены)?",
            )
            if r != QMessageBox.StandardButton.Yes:
                return
        self.accept()
