#image_canvas.py
from __future__ import annotations

from enum import Enum

import cv2
import numpy as np
from PIL import Image as PILImage
from PySide6.QtCore import Qt, QPoint, QPointF, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)


class Tool(Enum):
    SELECT = "select"
    POLYGON = "polygon"
    POLYGON_ERASER = "polygon_eraser"
    BRUSH = "brush"
    ERASER = "eraser"


_BRUSH_TOOLS = (Tool.BRUSH, Tool.ERASER)
_POLYGON_TOOLS = (Tool.POLYGON, Tool.POLYGON_ERASER)


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _make_lut(brightness: int, contrast: int, gamma: float) -> np.ndarray:
    lut = np.arange(256, dtype=np.float32)
    if gamma != 1.0:
        lut = np.power(lut / 255.0, 1.0 / gamma) * 255.0
    if contrast != 0:
        factor = (contrast + 100) / 100.0
        lut = (lut - 128.0) * factor + 128.0
    if brightness != 0:
        lut = lut + brightness
    return np.clip(lut, 0, 255).astype(np.uint8)


def _apply_clahe(arr: np.ndarray, clip: float, tile: int) -> np.ndarray:
    tile = max(2, int(tile))
    clahe = cv2.createCLAHE(clipLimit=float(clip), tileGridSize=(tile, tile))
    if arr.ndim == 2:
        return clahe.apply(arr)
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
    lab[..., 0] = clahe.apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def _apply_frangi(arr: np.ndarray) -> np.ndarray:
    from skimage.filters import frangi
    if arr.ndim == 3:
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    else:
        gray = arr
    response = frangi(gray.astype(np.float32) / 255.0, sigmas=range(1, 6))
    if response.max() > 0:
        normalized = (response / response.max() * 255.0).clip(0, 255).astype(
            np.uint8
        )
    else:
        normalized = np.zeros_like(response, dtype=np.uint8)
    return np.stack([normalized, normalized, normalized], axis=-1)


def _compose_diameter_heatmap(
    instances: dict[int, tuple[int | None, np.ndarray]],
    visible: set[int],
    layer_alpha: float,
) -> np.ndarray | None:
    visible_masks = [
        m
        for iid, (_lid, m) in instances.items()
        if iid in visible and m is not None
    ]
    if not visible_masks:
        return None
    from scipy.ndimage import distance_transform_edt
    from skimage.morphology import skeletonize

    h, w = visible_masks[0].shape
    rgb_acc = np.zeros((h, w, 3), dtype=np.float32)
    alpha_acc = np.zeros((h, w), dtype=np.float32)
    for mask in visible_masks:
        binary = (mask > 0).astype(np.uint8)
        if not binary.any():
            continue
        skel = skeletonize(binary.astype(bool))
        if not skel.any():
            continue
        dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
        inv_skel = ~skel
        _, idx = distance_transform_edt(inv_skel, return_indices=True)
        ny = idx[0]
        nx = idx[1]
        diameter_map = 2.0 * dist[ny, nx]
        diameter_map[binary == 0] = 0
        valid = diameter_map[binary > 0]
        if valid.size == 0:
            continue
        d_min = float(valid.min())
        d_max = float(valid.max())
        if d_max <= d_min:
            normalized = np.zeros_like(diameter_map, dtype=np.uint8)
        else:
            normalized = (
                (diameter_map - d_min) / (d_max - d_min) * 255.0
            ).clip(0, 255).astype(np.uint8)
        colored_bgr = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
        m_bool = binary > 0
        r = colored_bgr[..., 2]
        g = colored_bgr[..., 1]
        b = colored_bgr[..., 0]
        rgb_acc[m_bool, 0] = (
            rgb_acc[m_bool, 0] * (1 - layer_alpha) + r[m_bool] * layer_alpha
        )
        rgb_acc[m_bool, 1] = (
            rgb_acc[m_bool, 1] * (1 - layer_alpha) + g[m_bool] * layer_alpha
        )
        rgb_acc[m_bool, 2] = (
            rgb_acc[m_bool, 2] * (1 - layer_alpha) + b[m_bool] * layer_alpha
        )
        alpha_acc[m_bool] = (
            alpha_acc[m_bool] * (1 - layer_alpha) + layer_alpha
        )
    if alpha_acc.max() == 0:
        return None
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = np.clip(rgb_acc[..., 0], 0, 255)
    rgba[..., 1] = np.clip(rgb_acc[..., 1], 0, 255)
    rgba[..., 2] = np.clip(rgb_acc[..., 2], 0, 255)
    rgba[..., 3] = np.clip(alpha_acc * 255, 0, 255)
    return rgba


def _array_to_qpixmap_rgb(arr: np.ndarray) -> QPixmap:
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    qimage = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimage)


def _rgba_to_qpixmap(arr: np.ndarray) -> QPixmap:
    arr = np.ascontiguousarray(arr)
    h, w = arr.shape[:2]
    qimage = QImage(arr.data, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)


def _compose_overlay_instances(
    instances: dict[int, tuple[int | None, np.ndarray]],
    label_colors: dict[int, str],
    visible: set[int],
    layer_alpha: float,
) -> np.ndarray | None:
    visible_items = [
        (iid, lid, m)
        for iid, (lid, m) in instances.items()
        if iid in visible
        and lid is not None
        and lid != 0
        and lid in label_colors
    ]
    if not visible_items:
        return None
    h, w = visible_items[0][2].shape
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    alpha = np.zeros((h, w), dtype=np.float32)
    visible_items.sort(key=lambda x: x[0])
    for _iid, lid, mask in visible_items:
        m = mask > 0
        if not m.any():
            continue
        r, g, b = _hex_to_rgb(label_colors[lid])
        rgb[m, 0] = rgb[m, 0] * (1 - layer_alpha) + r * layer_alpha
        rgb[m, 1] = rgb[m, 1] * (1 - layer_alpha) + g * layer_alpha
        rgb[m, 2] = rgb[m, 2] * (1 - layer_alpha) + b * layer_alpha
        alpha[m] = alpha[m] * (1 - layer_alpha) + layer_alpha
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 0] = np.clip(rgb[..., 0], 0, 255)
    rgba[..., 1] = np.clip(rgb[..., 1], 0, 255)
    rgba[..., 2] = np.clip(rgb[..., 2], 0, 255)
    rgba[..., 3] = np.clip(alpha * 255, 0, 255)
    return rgba


def _build_outline_path(mask: np.ndarray) -> QPainterPath | None:
    if mask is None or not mask.any():
        return None
    contours, _ = cv2.findContours(
        (mask > 0).astype(np.uint8),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )
    if not contours:
        return None
    path = QPainterPath()
    for contour in contours:
        if len(contour) < 2:
            continue
        pts = contour.reshape(-1, 2)
        path.moveTo(float(pts[0][0]), float(pts[0][1]))
        for x, y in pts[1:]:
            path.lineTo(float(x), float(y))
        path.closeSubpath()
    return path


class ImageCanvas(QGraphicsView):
    ZOOM_FACTOR = 1.15
    OVERLAY_ALPHA = 0.55
    FREEHAND_TARGET_SCREEN_PX = 6
    EDGE_MARGIN = 20
    EDGE_SCROLL_DIVISOR = 4
    EDGE_TIMER_MS = 30
    VERTEX_RADIUS = 4
    RMB_INITIAL_DELAY_MS = 350
    RMB_REPEAT_MS = 60

    polygon_finished = Signal(list)
    brush_pressed = Signal(QPointF)
    brush_moved = Signal(QPointF, QPointF)
    brush_released = Signal()
    hover_instance_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._image_item: QGraphicsPixmapItem | None = None
        self._mask_item: QGraphicsPixmapItem | None = None
        self._poly_item: QGraphicsPathItem | None = None
        self._vertex_items: list[QGraphicsEllipseItem] = []
        self._brush_cursor_item: QGraphicsEllipseItem | None = None
        self._selection_item: QGraphicsPathItem | None = None
        self._hover_item: QGraphicsPathItem | None = None
        self._source_array: np.ndarray | None = None
        self._clahe_cache: np.ndarray | None = None
        self._frangi_cache: np.ndarray | None = None
        self._instances: dict[int, tuple[int | None, np.ndarray]] = {}
        self._visible_instances: set[int] = set()
        self._label_colors: dict[int, str] = {}
        self._brightness = 0
        self._contrast = 0
        self._gamma = 1.0
        self._clahe_enabled = False
        self._clahe_clip = 2.0
        self._clahe_tile = 8
        self._frangi_enabled = False
        self._diameter_map_enabled = False
        self._overlay_alpha = self.OVERLAY_ALPHA
        self._tool = Tool.SELECT
        self._poly_points: list[QPointF] = []
        self._freehand_active = False
        self._brush_size = 15
        self._brush_active = False
        self._brush_last_pt: QPointF | None = None
        self._selected_instance_id: int | None = None
        self._hover_instance_id: int | None = None

        self.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#2b2b2b"))
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self._update_drag_mode()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(30)
        self._refresh_timer.timeout.connect(self._refresh_image)

        self._edge_timer = QTimer(self)
        self._edge_timer.setInterval(self.EDGE_TIMER_MS)
        self._edge_timer.timeout.connect(self._auto_scroll)

        self._rmb_initial_timer = QTimer(self)
        self._rmb_initial_timer.setSingleShot(True)
        self._rmb_initial_timer.setInterval(self.RMB_INITIAL_DELAY_MS)
        self._rmb_initial_timer.timeout.connect(self._start_rmb_repeat)

        self._rmb_repeat_timer = QTimer(self)
        self._rmb_repeat_timer.setInterval(self.RMB_REPEAT_MS)
        self._rmb_repeat_timer.timeout.connect(self._delete_last_point)

    def set_image_path(self, path: str | None) -> None:
        if path is None:
            self._source_array = None
        else:
            try:
                with PILImage.open(path) as im:
                    if im.mode != "RGB":
                        im = im.convert("RGB")
                    self._source_array = np.array(im)
            except Exception:
                self._source_array = None
        self._clahe_cache = None
        self._frangi_cache = None
        self.cancel_polygon()
        self._set_hover_instance(None)
        self.resetTransform()
        self._refresh_image()
        self._update_brush_cursor()

    def set_instances(
        self,
        instances: dict[int, tuple[int | None, np.ndarray]],
        visible: set[int],
    ) -> None:
        self._instances = dict(instances)
        self._visible_instances = set(visible)
        self._refresh_mask()
        self._refresh_selection_outline()
        self._refresh_hover_outline()

    def set_visible_instances(self, visible: set[int]) -> None:
        self._visible_instances = set(visible)
        self._refresh_mask()
        self._refresh_selection_outline()
        self._refresh_hover_outline()

    def set_label_colors(self, colors: dict[int, str]) -> None:
        self._label_colors = dict(colors)
        self._refresh_mask()

    def set_selected_instance(self, instance_id: int | None) -> None:
        if instance_id == self._selected_instance_id:
            return
        self._selected_instance_id = instance_id
        self._refresh_selection_outline()
        self._refresh_hover_outline()

    def set_adjustments(
        self, brightness: int, contrast: int, gamma: float
    ) -> None:
        changed = (brightness, contrast, gamma) != (
            self._brightness,
            self._contrast,
            self._gamma,
        )
        self._brightness = brightness
        self._contrast = contrast
        self._gamma = gamma
        if changed:
            self._refresh_timer.start()

    def set_clahe(self, enabled: bool, clip: float, tile: int) -> None:
        changed = (enabled, clip, tile) != (
            self._clahe_enabled,
            self._clahe_clip,
            self._clahe_tile,
        )
        self._clahe_enabled = enabled
        self._clahe_clip = clip
        self._clahe_tile = tile
        if changed:
            self._clahe_cache = None
            self._refresh_timer.start()

    def set_frangi(self, enabled: bool) -> None:
        if enabled == self._frangi_enabled:
            return
        self._frangi_enabled = enabled
        self._clahe_cache = None
        self._refresh_timer.start()

    def set_diameter_map(self, enabled: bool) -> None:
        if enabled == self._diameter_map_enabled:
            return
        self._diameter_map_enabled = enabled
        self._refresh_mask()

    def set_overlay_alpha(self, alpha: float) -> None:
        alpha = max(0.0, min(1.0, float(alpha)))
        if alpha == self._overlay_alpha:
            return
        self._overlay_alpha = alpha
        self._refresh_mask()

    def set_tool(self, tool: Tool) -> None:
        if tool == self._tool:
            return
        self.cancel_polygon()
        self._brush_active = False
        self._brush_last_pt = None
        self._tool = tool
        self._update_drag_mode()
        if tool in _POLYGON_TOOLS:
            self._edge_timer.start()
        else:
            self._edge_timer.stop()
            self._rmb_initial_timer.stop()
            self._rmb_repeat_timer.stop()
        if tool != Tool.SELECT:
            self._set_hover_instance(None)
        self._update_brush_cursor()

    def current_tool(self) -> Tool:
        return self._tool

    def set_brush_size(self, size: int) -> None:
        self._brush_size = max(1, int(size))
        self._update_brush_cursor()

    def brush_size(self) -> int:
        return self._brush_size

    def _freehand_min_dist_sq(self) -> float:
        scale = self.transform().m11()
        if scale <= 0:
            scale = 1.0
        scene_dist = self.FREEHAND_TARGET_SCREEN_PX / scale
        return scene_dist * scene_dist

    def cancel_polygon(self) -> None:
        self._poly_points.clear()
        self._freehand_active = False
        self._rmb_initial_timer.stop()
        self._rmb_repeat_timer.stop()
        self._update_poly_preview()

    def finish_polygon(self) -> None:
        if self._tool not in _POLYGON_TOOLS or len(self._poly_points) < 3:
            self.cancel_polygon()
            return
        points = [(p.x(), p.y()) for p in self._poly_points]
        self._poly_points.clear()
        self._freehand_active = False
        self._update_poly_preview()
        self.polygon_finished.emit(points)

    def _delete_last_point(self) -> None:
        if self._poly_points:
            self._poly_points.pop()
            self._update_poly_preview()
        if not self._poly_points:
            self._rmb_repeat_timer.stop()

    def _start_rmb_repeat(self) -> None:
        if self._poly_points:
            self._rmb_repeat_timer.start()

    def _update_drag_mode(self) -> None:
        if self._tool == Tool.SELECT:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def _refresh_image(self) -> None:
        if self._image_item is not None:
            self._scene.removeItem(self._image_item)
            self._image_item = None
        if self._mask_item is not None:
            self._scene.removeItem(self._mask_item)
            self._mask_item = None
        if self._source_array is None:
            return
        base = self._source_array
        if self._frangi_enabled:
            if self._frangi_cache is None:
                from PySide6.QtWidgets import QApplication
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    self._frangi_cache = _apply_frangi(base)
                except Exception:
                    self._frangi_cache = base
                finally:
                    QApplication.restoreOverrideCursor()
            base = self._frangi_cache
        if self._clahe_enabled:
            if self._clahe_cache is None:
                try:
                    self._clahe_cache = _apply_clahe(
                        base, self._clahe_clip, self._clahe_tile
                    )
                except Exception:
                    self._clahe_cache = base
            arr = self._clahe_cache
        else:
            arr = base
        if (self._brightness, self._contrast, self._gamma) != (0, 0, 1.0):
            lut = _make_lut(self._brightness, self._contrast, self._gamma)
            arr = lut[arr]
        pixmap = _array_to_qpixmap_rgb(arr)
        if pixmap.isNull():
            return
        self._image_item = self._scene.addPixmap(pixmap)
        self._image_item.setZValue(0)
        self._scene.setSceneRect(self._image_item.boundingRect())
        if self.transform().isIdentity():
            self.fit_to_window()
        self._refresh_mask()
        self._refresh_selection_outline()
        self._refresh_hover_outline()

    def _refresh_mask(self) -> None:
        if self._mask_item is not None:
            self._scene.removeItem(self._mask_item)
            self._mask_item = None
        if self._image_item is None:
            return
        if self._diameter_map_enabled:
            try:
                rgba = _compose_diameter_heatmap(
                    self._instances,
                    self._visible_instances,
                    self._overlay_alpha,
                )
            except Exception:
                rgba = None
        else:
            rgba = _compose_overlay_instances(
                self._instances,
                self._label_colors,
                self._visible_instances,
                self._overlay_alpha,
            )
        if rgba is None:
            return
        pixmap = _rgba_to_qpixmap(rgba)
        self._mask_item = self._scene.addPixmap(pixmap)
        self._mask_item.setZValue(1)

    def _refresh_selection_outline(self) -> None:
        if self._selection_item is not None:
            self._scene.removeItem(self._selection_item)
            self._selection_item = None
        iid = self._selected_instance_id
        if iid is None or iid not in self._instances:
            return
        if iid not in self._visible_instances:
            return
        _lid, mask = self._instances[iid]
        path = _build_outline_path(mask)
        if path is None:
            return
        pen = QPen(QColor("#ffffff"), 2.5)
        pen.setCosmetic(True)
        self._selection_item = self._scene.addPath(path, pen)
        self._selection_item.setZValue(6)

    def _refresh_hover_outline(self) -> None:
        if self._hover_item is not None:
            self._scene.removeItem(self._hover_item)
            self._hover_item = None
        iid = self._hover_instance_id
        if iid is None or iid == self._selected_instance_id:
            return
        if iid not in self._instances or iid not in self._visible_instances:
            return
        _lid, mask = self._instances[iid]
        path = _build_outline_path(mask)
        if path is None:
            return
        pen = QPen(QColor("#ffeb3b"), 2.0)
        pen.setCosmetic(True)
        self._hover_item = self._scene.addPath(path, pen)
        self._hover_item.setZValue(5)

    def _set_hover_instance(self, iid: int | None) -> None:
        if iid == self._hover_instance_id:
            return
        self._hover_instance_id = iid
        self.hover_instance_changed.emit(iid if iid is not None else -1)
        self._refresh_hover_outline()

    def _instance_at(self, x: int, y: int) -> int | None:
        for iid in sorted(self._instances.keys(), reverse=True):
            if iid not in self._visible_instances:
                continue
            _lid, mask = self._instances[iid]
            if 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1]:
                if mask[y, x] > 0:
                    return iid
        return None

    def _update_poly_preview(self) -> None:
        if self._poly_item is not None:
            self._scene.removeItem(self._poly_item)
            self._poly_item = None
        for v in self._vertex_items:
            self._scene.removeItem(v)
        self._vertex_items.clear()
        if not self._poly_points:
            return
        path = QPainterPath()
        path.moveTo(self._poly_points[0])
        for pt in self._poly_points[1:]:
            path.lineTo(pt)
        if len(self._poly_points) >= 3:
            path.lineTo(self._poly_points[0])
        line_color = (
            QColor("#ff5252") if self._tool == Tool.POLYGON_ERASER else QColor("#ffeb3b")
        )
        pen = QPen(line_color, 2)
        pen.setCosmetic(True)
        self._poly_item = self._scene.addPath(path, pen)
        self._poly_item.setZValue(10)
        if not self._freehand_active:
            r = self.VERTEX_RADIUS
            brush = QBrush(line_color)
            border = QPen(QColor("#000"), 1)
            for pt in self._poly_points:
                ell = QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
                ell.setPos(pt)
                ell.setBrush(brush)
                ell.setPen(border)
                ell.setFlag(
                    QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,
                    True,
                )
                ell.setZValue(11)
                self._scene.addItem(ell)
                self._vertex_items.append(ell)

    def _ensure_brush_cursor(self) -> None:
        if self._brush_cursor_item is not None:
            return
        item = QGraphicsEllipseItem()
        item.setZValue(20)
        item.setBrush(Qt.BrushStyle.NoBrush)
        self._scene.addItem(item)
        self._brush_cursor_item = item

    def _update_brush_cursor(self) -> None:
        if self._tool not in _BRUSH_TOOLS:
            if self._brush_cursor_item is not None:
                self._brush_cursor_item.setVisible(False)
            return
        pos = self.viewport().mapFromGlobal(QCursor.pos())
        self._update_brush_cursor_at(pos)

    def _update_brush_cursor_at(self, viewport_pos: QPoint) -> None:
        if self._tool not in _BRUSH_TOOLS:
            if self._brush_cursor_item is not None:
                self._brush_cursor_item.setVisible(False)
            return
        if self._image_item is None:
            return
        self._ensure_brush_cursor()
        item = self._brush_cursor_item
        assert item is not None
        if not self.viewport().rect().contains(viewport_pos):
            item.setVisible(False)
            return
        scene_pt = self.mapToScene(viewport_pos)
        r = self._brush_size / 2
        item.setRect(-r, -r, self._brush_size, self._brush_size)
        item.setPos(scene_pt)
        color = (
            QColor("#ffeb3b") if self._tool == Tool.BRUSH else QColor("#ff5252")
        )
        pen = QPen(color, 1.5)
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setVisible(True)

    def _auto_scroll(self) -> None:
        if self._tool not in _POLYGON_TOOLS:
            return
        viewport = self.viewport()
        cursor_in_view = viewport.mapFromGlobal(QCursor.pos())
        rect = viewport.rect()
        if not rect.contains(cursor_in_view):
            return
        margin = self.EDGE_MARGIN
        div = self.EDGE_SCROLL_DIVISOR
        dx = dy = 0
        if cursor_in_view.x() < margin:
            dx = -((margin - cursor_in_view.x()) // div + 1)
        elif cursor_in_view.x() > rect.width() - margin:
            dx = (cursor_in_view.x() - (rect.width() - margin)) // div + 1
        if cursor_in_view.y() < margin:
            dy = -((margin - cursor_in_view.y()) // div + 1)
        elif cursor_in_view.y() > rect.height() - margin:
            dy = (cursor_in_view.y() - (rect.height() - margin)) // div + 1
        if dx == 0 and dy == 0:
            return
        hbar = self.horizontalScrollBar()
        vbar = self.verticalScrollBar()
        hbar.setValue(hbar.value() + dx)
        vbar.setValue(vbar.value() + dy)
        if self._freehand_active:
            scene_pt = self.mapToScene(cursor_in_view)
            if self._poly_points:
                last = self._poly_points[-1]
                ddx = scene_pt.x() - last.x()
                ddy = scene_pt.y() - last.y()
                if ddx * ddx + ddy * ddy < self._freehand_min_dist_sq():
                    return
            self._poly_points.append(scene_pt)
            self._update_poly_preview()

    def fit_to_window(self) -> None:
        if self._image_item is None:
            return
        self.fitInView(
            self._image_item.boundingRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def zoom_in(self) -> None:
        self.scale(self.ZOOM_FACTOR, self.ZOOM_FACTOR)

    def zoom_out(self) -> None:
        self.scale(1 / self.ZOOM_FACTOR, 1 / self.ZOOM_FACTOR)

    def reset_zoom(self) -> None:
        self.resetTransform()
        self.fit_to_window()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._freehand_active or self._brush_active:
            event.accept()
            return
        factor = (
            self.ZOOM_FACTOR
            if event.angleDelta().y() > 0
            else 1 / self.ZOOM_FACTOR
        )
        self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._tool in _POLYGON_TOOLS:
            if event.button() == Qt.MouseButton.LeftButton:
                with_shift = bool(
                    event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                )
                pt = self.mapToScene(event.pos())
                if with_shift:
                    self._freehand_active = True
                self._poly_points.append(pt)
                self._update_poly_preview()
                event.accept()
                return
            if event.button() == Qt.MouseButton.RightButton:
                self._delete_last_point()
                if self._poly_points:
                    self._rmb_initial_timer.start()
                event.accept()
                return
        elif self._tool in _BRUSH_TOOLS:
            if event.button() == Qt.MouseButton.LeftButton:
                scene_pt = self.mapToScene(event.pos())
                self._brush_active = True
                self._brush_last_pt = scene_pt
                self.brush_pressed.emit(scene_pt)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._tool in _BRUSH_TOOLS:
            self._update_brush_cursor_at(event.pos())
            if self._brush_active:
                scene_pt = self.mapToScene(event.pos())
                last = self._brush_last_pt
                self._brush_last_pt = scene_pt
                if last is not None:
                    self.brush_moved.emit(last, scene_pt)
                event.accept()
                return
        elif self._tool in _POLYGON_TOOLS and self._freehand_active:
            pt = self.mapToScene(event.pos())
            if self._poly_points:
                last = self._poly_points[-1]
                dx = pt.x() - last.x()
                dy = pt.y() - last.y()
                if dx * dx + dy * dy < self._freehand_min_dist_sq():
                    event.accept()
                    return
            self._poly_points.append(pt)
            self._update_poly_preview()
            event.accept()
            return
        elif self._tool == Tool.SELECT and self._image_item is not None:
            scene_pt = self.mapToScene(event.pos())
            x = int(round(scene_pt.x()))
            y = int(round(scene_pt.y()))
            iid = self._instance_at(x, y)
            self._set_hover_instance(iid)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._tool in _POLYGON_TOOLS and self._freehand_active:
                self._freehand_active = False
                if len(self._poly_points) < 3:
                    self.cancel_polygon()
                else:
                    self._update_poly_preview()
                event.accept()
                return
            if self._tool in _BRUSH_TOOLS and self._brush_active:
                self._brush_active = False
                self._brush_last_pt = None
                self.brush_released.emit()
                event.accept()
                return
        elif event.button() == Qt.MouseButton.RightButton:
            if self._tool in _POLYGON_TOOLS:
                self._rmb_initial_timer.stop()
                self._rmb_repeat_timer.stop()
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        if self._brush_cursor_item is not None:
            self._brush_cursor_item.setVisible(False)
        if self._tool == Tool.SELECT:
            self._set_hover_instance(None)
        super().leaveEvent(event)
