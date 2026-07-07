#task_workspace.py

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image as PILImage
from PySide6.QtCore import Qt, QPointF, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtWidgets import QApplication, QDialog, QProgressDialog

from src.annotator.core.annotation_commands import (
    ChangeClassCommand,
    CreateInstanceCommand,
    DeleteInstanceCommand,
    ModifyMaskCommand,
)
from src.annotator.core.app_paths import app_root
from src.annotator.core.commands import Command, CommandHistory, CompositeCommand
from src.annotator.core.mask_storage import (
    delete_mask_file,
    discover_instance_masks,
    instance_mask_filename,
    load_binary_mask,
    save_binary_mask,
)
from src.annotator.core.models import AnnotationInstance, Image, Label as LabelModel
from src.annotator.core.project import Project
from src.annotator.ui.adjustments_panel import AdjustmentsPanel
from src.annotator.ui.ai_dialog import AiDialog, AiProgressDialog
from src.annotator.ui.classes_panel import ClassesPanel
from src.annotator.ui.image_canvas import ImageCanvas, Tool
from src.annotator.ui.image_list_view import ImageListView
from src.annotator.ui.objects_panel import ObjectEntry, ObjectsPanel


class TaskWorkspace(QWidget):
    back_requested = Signal()
    image_position_changed = Signal(int, int, str)

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._task_id: int | None = None
        self._total: int = 0
        self._current_row: int = -1
        self._current_image: Image | None = None
        self._current_instances: dict[int, tuple[int | None, np.ndarray]] = {}
        self._visible_instances: set[int] = set()
        self._active_label: LabelModel | None = None
        self._updating: bool = False
        self._brush_size: int = 15
        self._brush_target_instance: int | None = None
        self._brush_modified_instances: set[int] = set()
        self._brush_refresh_pending: bool = False
        self._eraser_all_mode: bool = False
        self._stroke_snapshots: dict[int, np.ndarray] = {}
        self._stroke_new_instances: dict[int, str] = {}
        self._histories: dict[int, CommandHistory] = {}
        self._build_ui()
        self._setup_shortcuts()
        self.canvas.polygon_finished.connect(self._on_polygon_finished)
        self.canvas.brush_pressed.connect(self._on_brush_pressed)
        self.canvas.brush_moved.connect(self._on_brush_moved)
        self.canvas.brush_released.connect(self._on_brush_released)
        self.canvas.hover_instance_changed.connect(self._on_hover_instance)
        self.objects_panel.selection_changed.connect(self._on_object_selection)
        self._brush_paint_timer = QTimer(self)
        self._brush_paint_timer.setSingleShot(True)
        self._brush_paint_timer.setInterval(33)
        self._brush_paint_timer.timeout.connect(self._do_brush_refresh)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top = QHBoxLayout()
        back_btn = QPushButton("← К задачам")
        back_btn.clicked.connect(self.back_requested.emit)
        top.addWidget(back_btn)

        self.tool_select_btn = QPushButton("🖱  Выбрать [V]")
        self.tool_select_btn.setCheckable(True)
        self.tool_select_btn.setChecked(True)
        self.tool_select_btn.clicked.connect(lambda: self._set_tool(Tool.SELECT))
        top.addWidget(self.tool_select_btn)

        self.tool_polygon_btn = QPushButton("⬡  Полигон [P]")
        self.tool_polygon_btn.setCheckable(True)
        self.tool_polygon_btn.clicked.connect(lambda: self._set_tool(Tool.POLYGON))
        top.addWidget(self.tool_polygon_btn)

        self.tool_poly_eraser_btn = QPushButton("⬡✕  Полигон-ластик [L]")
        self.tool_poly_eraser_btn.setCheckable(True)
        self.tool_poly_eraser_btn.clicked.connect(
            lambda: self._set_tool(Tool.POLYGON_ERASER)
        )
        top.addWidget(self.tool_poly_eraser_btn)

        self.tool_brush_btn = QPushButton("🖌  Кисть [B]")
        self.tool_brush_btn.setCheckable(True)
        self.tool_brush_btn.clicked.connect(lambda: self._set_tool(Tool.BRUSH))
        top.addWidget(self.tool_brush_btn)

        self.tool_eraser_btn = QPushButton("🩹  Ластик [E]")
        self.tool_eraser_btn.setCheckable(True)
        self.tool_eraser_btn.clicked.connect(lambda: self._set_tool(Tool.ERASER))
        top.addWidget(self.tool_eraser_btn)

        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_group.addButton(self.tool_select_btn)
        self._tool_group.addButton(self.tool_polygon_btn)
        self._tool_group.addButton(self.tool_poly_eraser_btn)
        self._tool_group.addButton(self.tool_brush_btn)
        self._tool_group.addButton(self.tool_eraser_btn)

        self.close_poly_btn = QPushButton("Замкнуть [Enter]")
        self.close_poly_btn.setToolTip("Замкнуть полигон")
        self.close_poly_btn.clicked.connect(lambda: self.canvas.finish_polygon())
        self.close_poly_btn.setVisible(False)
        top.addWidget(self.close_poly_btn)

        self.ai_btn = QPushButton("🤖 AI разметка…")
        self.ai_btn.setToolTip("Запустить нейросеть из папки models/")
        self.ai_btn.clicked.connect(self._on_ai_action)
        top.addWidget(self.ai_btn)

        self.brush_size_label = QLabel("Размер:")
        self.brush_size_label.setVisible(False)
        top.addWidget(self.brush_size_label)
        self.brush_size_spin = QSpinBox()
        self.brush_size_spin.setRange(1, 500)
        self.brush_size_spin.setValue(self._brush_size)
        self.brush_size_spin.setSuffix(" px")
        self.brush_size_spin.setVisible(False)
        self.brush_size_spin.valueChanged.connect(self._on_brush_size_changed)
        top.addWidget(self.brush_size_spin)

        top.addWidget(QLabel("Класс:"))
        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(180)
        self.class_combo.currentIndexChanged.connect(self._on_class_combo_changed)
        top.addWidget(self.class_combo)

        self.task_label = QLabel("")
        self.task_label.setStyleSheet(
            "font-weight: bold; padding-left: 12px; font-size: 12pt;"
        )
        top.addWidget(self.task_label)
        top.addStretch()

        self.hover_label = QLabel("")
        self.hover_label.setStyleSheet("padding: 4px 8px; color: #555;")
        top.addWidget(self.hover_label)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.image_list = ImageListView()
        self.image_list.image_selected.connect(self._on_image_selected)
        splitter.addWidget(self.image_list)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        nav = QHBoxLayout()
        self.first_btn = QPushButton("⏮")
        self.first_btn.setToolTip("К первому изображению")
        self.first_btn.setFixedWidth(36)
        self.first_btn.clicked.connect(lambda: self._set_position(0))
        nav.addWidget(self.first_btn)

        self.prev_btn = QPushButton("◀")
        self.prev_btn.setToolTip("Предыдущее")
        self.prev_btn.setFixedWidth(36)
        self.prev_btn.clicked.connect(
            lambda: self._set_position(self._current_row - 1)
        )
        nav.addWidget(self.prev_btn)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(1)
        self.slider.setMaximum(1)
        self.slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.slider.valueChanged.connect(self._on_slider_changed)
        nav.addWidget(self.slider, stretch=1)

        self.spinbox = QSpinBox()
        self.spinbox.setMinimum(1)
        self.spinbox.setMaximum(1)
        self.spinbox.setFixedWidth(80)
        self.spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        nav.addWidget(self.spinbox)

        self.total_label = QLabel("/ 0")
        self.total_label.setStyleSheet("padding: 0 4px;")
        nav.addWidget(self.total_label)

        self.next_btn = QPushButton("▶")
        self.next_btn.setToolTip("Следующее")
        self.next_btn.setFixedWidth(36)
        self.next_btn.clicked.connect(
            lambda: self._set_position(self._current_row + 1)
        )
        nav.addWidget(self.next_btn)

        self.last_btn = QPushButton("⏭")
        self.last_btn.setToolTip("К последнему изображению")
        self.last_btn.setFixedWidth(36)
        self.last_btn.clicked.connect(lambda: self._set_position(self._total - 1))
        nav.addWidget(self.last_btn)

        right_layout.addLayout(nav)

        self.filename_label = QLabel("")
        self.filename_label.setStyleSheet(
            "font-size: 11pt; padding: 4px; border: 1px solid #ccc;"
        )
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_layout.addWidget(self.filename_label)

        self.canvas = ImageCanvas()
        self.canvas.set_brush_size(self._brush_size)
        right_layout.addWidget(self.canvas, stretch=1)

        splitter.addWidget(right_widget)

        self.right_tabs = QTabWidget()

        self.objects_panel = ObjectsPanel()
        self.objects_panel.visibility_changed.connect(self._on_object_visibility)
        self.objects_panel.delete_requested.connect(self._on_object_delete)
        self.objects_panel.change_class_requested.connect(self._on_object_change_class)
        self.right_tabs.addTab(self.objects_panel, "Объекты")

        self.classes_panel = ClassesPanel()
        self.classes_panel.active_label_changed.connect(
            self._on_classes_panel_active_changed
        )
        self.classes_panel.labels_changed.connect(self._on_labels_changed)
        self.right_tabs.addTab(self.classes_panel, "Классы")

        self.adjustments_panel = AdjustmentsPanel()
        self.adjustments_panel.adjustments_changed.connect(
            self._on_adjustments_changed
        )
        self.adjustments_panel.clahe_changed.connect(self._on_clahe_changed)
        self.adjustments_panel.frangi_changed.connect(self._on_frangi_changed)
        self.adjustments_panel.diameter_map_changed.connect(
            self._on_diameter_map_changed
        )
        self.adjustments_panel.opacity_changed.connect(
            self._on_opacity_changed
        )
        self.right_tabs.addTab(self.adjustments_panel, "Отображение")

        splitter.addWidget(self.right_tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([220, 800, 260])
        layout.addWidget(splitter, stretch=1)

    def _setup_shortcuts(self) -> None:
        self._make_shortcut("Left", lambda: self._set_position(self._current_row - 1))
        self._make_shortcut("Right", lambda: self._set_position(self._current_row + 1))
        self._make_shortcut("Home", lambda: self._set_position(0))
        self._make_shortcut("End", lambda: self._set_position(self._total - 1))
        self._make_shortcut("Ctrl+=", self.canvas.zoom_in)
        self._make_shortcut("Ctrl++", self.canvas.zoom_in)
        self._make_shortcut("Ctrl+-", self.canvas.zoom_out)
        self._make_shortcut("Ctrl+0", self.canvas.reset_zoom)
        self._make_shortcut("V", lambda: self._set_tool(Tool.SELECT))
        self._make_shortcut("P", lambda: self._set_tool(Tool.POLYGON))
        self._make_shortcut("L", lambda: self._set_tool(Tool.POLYGON_ERASER))
        self._make_shortcut("B", lambda: self._set_tool(Tool.BRUSH))
        self._make_shortcut("E", lambda: self._set_tool(Tool.ERASER))
        self._make_shortcut("Escape", self.canvas.cancel_polygon)
        self._make_shortcut("Return", self.canvas.finish_polygon)
        self._make_shortcut("Enter", self.canvas.finish_polygon)
        self._make_shortcut("[", lambda: self._adjust_brush_size(-2))
        self._make_shortcut("]", lambda: self._adjust_brush_size(2))
        self._make_shortcut("Ctrl+Z", self._on_undo)
        self._make_shortcut("Ctrl+Shift+Z", self._on_redo)
        self._make_shortcut("Ctrl+Y", self._on_redo)

    def _make_shortcut(self, key: str, slot) -> None:
        sc = QShortcut(QKeySequence(key), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(slot)

    def set_task(self, project: Project, task_id: int, task_name: str) -> None:
        self._project = project
        self._task_id = task_id
        self._current_row = -1
        self._current_image = None
        self._current_instances = {}
        self._visible_instances = set()
        self._histories = {}
        self.task_label.setText(task_name)
        self.image_list.set_task(project, task_id)
        model = self.image_list.model()
        self._total = model.rowCount() if model is not None else 0

        self._updating = True
        try:
            self.slider.setMaximum(max(1, self._total))
            self.spinbox.setMaximum(max(1, self._total))
            self.total_label.setText(f"/ {self._total}")
        finally:
            self._updating = False

        self.classes_panel.set_project(project)
        self._update_label_colors()
        self._refresh_class_combo()
        self._load_adjustments(project)
        self._set_tool(Tool.SELECT)

        if self._total == 0:
            self.canvas.set_image_path(None)
            self.canvas.set_instances({}, set())
            self.filename_label.setText("")
            self._refresh_objects_panel()
            self._update_nav_buttons()
            self.image_position_changed.emit(0, 0, "")
            return

        start_row = 0
        last_image_id = project.repo.get_last_image(task_id)
        if last_image_id is not None and model is not None:
            for i in range(self._total):
                img = model.image_at(i)
                if img is not None and img.id == last_image_id:
                    start_row = i
                    break
        self._set_position(start_row)

    def clear(self) -> None:
        self._project = None
        self._task_id = None
        self._total = 0
        self._current_row = -1
        self._current_image = None
        self._current_instances = {}
        self._visible_instances = set()
        self._active_label = None
        self._histories = {}
        self.task_label.setText("")
        self.canvas.set_image_path(None)
        self.canvas.set_instances({}, set())
        self.canvas.set_selected_instance(None)
        self.filename_label.setText("")
        self.image_list.set_task(None, None)
        self.classes_panel.set_project(None)
        self._refresh_class_combo()
        self._refresh_objects_panel()
        self.hover_label.setText("")
        self._updating = True
        try:
            self.slider.setMaximum(1)
            self.slider.setValue(1)
            self.spinbox.setMaximum(1)
            self.spinbox.setValue(1)
            self.total_label.setText("/ 0")
        finally:
            self._updating = False
        self._update_nav_buttons()
        self.image_position_changed.emit(0, 0, "")

    def refresh_thumbnails(self) -> None:
        self.image_list.refresh_thumbnails()

    def _load_adjustments(self, project: Project) -> None:
        try:
            b = int(project.repo.get_meta("display:brightness") or "0")
        except ValueError:
            b = 0
        try:
            c = int(project.repo.get_meta("display:contrast") or "0")
        except ValueError:
            c = 0
        try:
            g = float(project.repo.get_meta("display:gamma") or "1.0")
        except ValueError:
            g = 1.0
        self.adjustments_panel.set_lut(b, c, g)
        clahe_on = (project.repo.get_meta("display:clahe_on") or "0") == "1"
        try:
            clip = float(project.repo.get_meta("display:clahe_clip") or "2.0")
        except ValueError:
            clip = 2.0
        try:
            tile = int(project.repo.get_meta("display:clahe_tile") or "8")
        except ValueError:
            tile = 8
        self.adjustments_panel.set_clahe(clahe_on, clip, tile)
        frangi_on = (project.repo.get_meta("display:frangi_on") or "0") == "1"
        self.adjustments_panel.set_frangi(frangi_on)
        diameter_on = (
            project.repo.get_meta("display:diameter_map_on") or "0"
        ) == "1"
        self.adjustments_panel.set_diameter_map(diameter_on)
        try:
            opacity = float(
                project.repo.get_meta("display:overlay_alpha") or "0.55"
            )
        except ValueError:
            opacity = 0.55
        self.adjustments_panel.set_opacity(opacity)

    def _on_adjustments_changed(
        self, brightness: int, contrast: int, gamma: float
    ) -> None:
        self.canvas.set_adjustments(brightness, contrast, gamma)
        if self._project is not None:
            self._project.repo.set_meta("display:brightness", str(brightness))
            self._project.repo.set_meta("display:contrast", str(contrast))
            self._project.repo.set_meta("display:gamma", str(gamma))

    def _on_clahe_changed(
        self, enabled: bool, clip: float, tile: int
    ) -> None:
        self.canvas.set_clahe(enabled, clip, tile)
        if self._project is not None:
            self._project.repo.set_meta("display:clahe_on", "1" if enabled else "0")
            self._project.repo.set_meta("display:clahe_clip", f"{clip:.3f}")
            self._project.repo.set_meta("display:clahe_tile", str(int(tile)))

    def _on_frangi_changed(self, enabled: bool) -> None:
        self.canvas.set_frangi(enabled)
        if self._project is not None:
            self._project.repo.set_meta(
                "display:frangi_on", "1" if enabled else "0"
            )

    def _on_diameter_map_changed(self, enabled: bool) -> None:
        self.canvas.set_diameter_map(enabled)
        if self._project is not None:
            self._project.repo.set_meta(
                "display:diameter_map_on", "1" if enabled else "0"
            )

    def _on_opacity_changed(self, alpha: float) -> None:
        self.canvas.set_overlay_alpha(alpha)
        if self._project is not None:
            self._project.repo.set_meta(
                "display:overlay_alpha", f"{alpha:.3f}"
            )

    def _set_tool(self, tool: Tool) -> None:
        self.canvas.set_tool(tool)
        if tool == Tool.SELECT:
            self.tool_select_btn.setChecked(True)
        elif tool == Tool.POLYGON:
            self.tool_polygon_btn.setChecked(True)
        elif tool == Tool.POLYGON_ERASER:
            self.tool_poly_eraser_btn.setChecked(True)
        elif tool == Tool.BRUSH:
            self.tool_brush_btn.setChecked(True)
        elif tool == Tool.ERASER:
            self.tool_eraser_btn.setChecked(True)
        is_polygon = tool in (Tool.POLYGON, Tool.POLYGON_ERASER)
        self.close_poly_btn.setVisible(is_polygon)
        show_brush = tool in (Tool.BRUSH, Tool.ERASER)
        self.brush_size_label.setVisible(show_brush)
        self.brush_size_spin.setVisible(show_brush)
        if tool != Tool.SELECT:
            self.hover_label.setText("")

    def _on_brush_size_changed(self, value: int) -> None:
        self._brush_size = max(1, int(value))
        self.canvas.set_brush_size(self._brush_size)

    def _adjust_brush_size(self, delta: int) -> None:
        new_size = max(1, min(500, self._brush_size + delta))
        if new_size == self._brush_size:
            return
        self.brush_size_spin.setValue(new_size)

    def _on_classes_panel_active_changed(
        self, label: LabelModel | None
    ) -> None:
        if self._updating:
            return
        self._active_label = label
        self._sync_combo_to_active()

    def _on_class_combo_changed(self, index: int) -> None:
        if self._updating:
            return
        label_id = self.class_combo.itemData(index)
        if label_id is None:
            self._active_label = None
        elif self._project is not None:
            for lbl in self._project.repo.list_labels():
                if lbl.id == label_id:
                    self._active_label = lbl
                    break
        self._updating = True
        try:
            self.classes_panel.set_active_label_id(label_id)
        finally:
            self._updating = False

    def _sync_combo_to_active(self) -> None:
        target_id = self._active_label.id if self._active_label else None
        self._updating = True
        try:
            for i in range(self.class_combo.count()):
                if self.class_combo.itemData(i) == target_id:
                    self.class_combo.setCurrentIndex(i)
                    return
            self.class_combo.setCurrentIndex(0)
        finally:
            self._updating = False

    def _refresh_class_combo(self) -> None:
        self._updating = True
        try:
            current_id = (
                self._active_label.id if self._active_label is not None else None
            )
            self.class_combo.clear()
            self.class_combo.addItem("(не выбран)", None)
            if self._project is not None:
                for label in self._project.repo.list_labels():
                    if label.id == 0:
                        continue
                    pm = QPixmap(16, 16)
                    pm.fill(QColor(label.color))
                    self.class_combo.addItem(QIcon(pm), label.name, label.id)
            for i in range(self.class_combo.count()):
                if self.class_combo.itemData(i) == current_id:
                    self.class_combo.setCurrentIndex(i)
                    break
        finally:
            self._updating = False

    def _on_labels_changed(self) -> None:
        self._update_label_colors()
        self._refresh_class_combo()
        self._refresh_objects_panel()

    def _update_label_colors(self) -> None:
        if self._project is None:
            self.canvas.set_label_colors({})
            return
        labels = self._project.repo.list_labels()
        colors = {label.id: label.color for label in labels}
        self.canvas.set_label_colors(colors)

    def _current_history(self) -> CommandHistory | None:
        if self._current_image is None:
            return None
        iid = self._current_image.id
        if iid not in self._histories:
            self._histories[iid] = CommandHistory()
        return self._histories[iid]

    def _push_command(self, command: Command) -> None:
        h = self._current_history()
        if h is not None:
            h.push(command)

    def _push_commands(self, commands: list[Command]) -> None:
        if not commands:
            return
        if len(commands) == 1:
            self._push_command(commands[0])
        else:
            self._push_command(CompositeCommand(commands))

    def _on_undo(self) -> None:
        h = self._current_history()
        if h is None or not h.can_undo():
            return
        h.undo()
        self._after_command()

    def _on_redo(self) -> None:
        h = self._current_history()
        if h is None or not h.can_redo():
            return
        h.redo()
        self._after_command()

    def _after_command(self) -> None:
        self.canvas.set_instances(
            self._current_instances, self._visible_instances
        )
        self._refresh_objects_panel()

    def _set_position(self, row: int) -> None:
        if self._updating or self._total == 0:
            return
        row = max(0, min(self._total - 1, row))
        if row == self._current_row:
            return
        self._current_row = row
        model = self.image_list.model()
        img = model.image_at(row) if model is not None else None
        self._current_image = img

        self._updating = True
        try:
            self.image_list.select_row(row)
            self.slider.setValue(row + 1)
            self.spinbox.setValue(row + 1)
        finally:
            self._updating = False

        if img is not None:
            self.canvas.set_image_path(img.source_path)
            self.filename_label.setText(img.filename)
            self.image_position_changed.emit(row + 1, self._total, img.filename)
            if self._project is not None and self._task_id is not None:
                self._project.repo.set_last_image(self._task_id, img.id)
            self._load_instances_for_current()
        self._update_nav_buttons()

    def _image_shape(self, img: Image) -> tuple[int, int] | None:
        if img.width and img.height:
            return img.height, img.width
        try:
            with PILImage.open(img.source_path) as im:
                return im.height, im.width
        except Exception:
            return None

    def _load_instances_for_current(self) -> None:
        if self._project is None or self._current_image is None:
            self._current_instances = {}
            self._visible_instances = set()
            self.canvas.set_instances({}, set())
            self._refresh_objects_panel()
            return
        img = self._current_image
        shape = self._image_shape(img)
        if shape is None:
            self._current_instances = {}
            self._visible_instances = set()
            self.canvas.set_instances({}, set())
            self._refresh_objects_panel()
            return
        records = self._project.repo.list_instances_for_image(img.id)
        discovered = discover_instance_masks(self._project.masks_dir, img.id)
        instances: dict[int, tuple[int | None, np.ndarray]] = {}
        for rec in records:
            if rec.instance_id not in discovered:
                continue
            path = self._project.masks_dir / discovered[rec.instance_id]
            mask = load_binary_mask(path, shape)
            instances[rec.instance_id] = (rec.label_id, mask)
        self._current_instances = instances
        self._visible_instances = set(instances.keys())
        self.canvas.set_instances(instances, self._visible_instances)
        self._refresh_objects_panel(records)

    def _refresh_objects_panel(
        self, records: list[AnnotationInstance] | None = None
    ) -> None:
        if self._project is None or self._current_image is None:
            self.objects_panel.set_data([], {}, [])
            return
        if records is None:
            records = self._project.repo.list_instances_for_image(
                self._current_image.id
            )
        labels = self._project.repo.list_labels()
        label_by_id = {l.id: l for l in labels}
        per_class_counter: dict[int | None, int] = {}
        entries: list[ObjectEntry] = []
        for rec in records:
            per_class_counter[rec.label_id] = (
                per_class_counter.get(rec.label_id, 0) + 1
            )
            lbl = label_by_id.get(rec.label_id) if rec.label_id is not None else None
            entries.append(
                ObjectEntry(
                    instance_id=rec.instance_id,
                    label_id=rec.label_id,
                    label_name=lbl.name if lbl else "(нет класса)",
                    label_color=lbl.color if lbl else "#888888",
                    per_class_index=per_class_counter[rec.label_id],
                )
            )
        visibility = {
            iid: (iid in self._visible_instances)
            for iid in (e.instance_id for e in entries)
        }
        available = [l for l in labels if l.id != 0]
        self.objects_panel.set_data(entries, visibility, available)

    def _on_object_selection(self, instance_id: int) -> None:
        sel = instance_id if instance_id >= 0 else None
        self.canvas.set_selected_instance(sel)

    def _on_hover_instance(self, instance_id: int) -> None:
        if instance_id < 0 or instance_id not in self._current_instances:
            self.hover_label.setText("")
            return
        lid, _ = self._current_instances[instance_id]
        label_name = "?"
        if lid is not None and self._project is not None:
            for l in self._project.repo.list_labels():
                if l.id == lid:
                    label_name = l.name
                    break
        self.hover_label.setText(f"Объект #{instance_id}: {label_name}")

    def _ensure_image_annotated(self, annotated: bool) -> None:
        if self._project is None or self._current_image is None:
            return
        if self._current_image.is_annotated == annotated:
            return
        self._project.repo.update_image_annotated(
            self._current_image.id, annotated
        )
        self._current_image = Image(
            id=self._current_image.id,
            task_id=self._current_image.task_id,
            filename=self._current_image.filename,
            source_path=self._current_image.source_path,
            width=self._current_image.width,
            height=self._current_image.height,
            mask_filename=self._current_image.mask_filename,
            thumbnail_filename=self._current_image.thumbnail_filename,
            order_index=self._current_image.order_index,
            is_annotated=annotated,
        )

    def _on_polygon_finished(self, points: list) -> None:
        tool = self.canvas.current_tool()
        if tool == Tool.POLYGON:
            self._handle_polygon_create(points)
        elif tool == Tool.POLYGON_ERASER:
            self._handle_polygon_erase(points)

    def _handle_polygon_create(self, points: list) -> None:
        if self._active_label is None or self._active_label.id == 0:
            QMessageBox.information(
                self,
                "Нет активного класса",
                "Выбери класс на вкладке «Классы» или в выпадающем списке сверху.",
            )
            return
        if self._project is None or self._current_image is None:
            return
        shape = self._image_shape(self._current_image)
        if shape is None or len(points) < 3:
            return
        result = self._create_polygon_instance(
            points, self._active_label.id, shape
        )
        if result is None:
            return
        instance_id, created_at = result
        _lid, mask = self._current_instances[instance_id]
        self._ensure_image_annotated(True)
        self.canvas.set_instances(
            self._current_instances, self._visible_instances
        )
        self._refresh_objects_panel()
        self._push_command(CreateInstanceCommand(
            self, instance_id, self._current_image.id,
            self._active_label.id, mask.copy(), created_at,
        ))

    def _create_polygon_instance(
        self,
        points: list,
        label_id: int,
        shape: tuple[int, int],
    ) -> tuple[int, str] | None:
        if (
            self._project is None
            or self._current_image is None
            or len(points) < 3
        ):
            return None
        instance_id, created_at = self._project.repo.create_instance(
            self._current_image.id, label_id
        )
        mask = np.zeros(shape, dtype=np.uint8)
        pts = np.array(
            [[int(round(x)), int(round(y))] for x, y in points], dtype=np.int32
        )
        cv2.fillPoly(mask, [pts], 1)
        filename = instance_mask_filename(self._current_image.id, instance_id)
        try:
            save_binary_mask(self._project.masks_dir / filename, mask)
        except Exception:
            self._project.repo.delete_instance(instance_id)
            return None
        self._current_instances[instance_id] = (label_id, mask)
        self._visible_instances.add(instance_id)
        return instance_id, created_at

    def _on_ai_action(self) -> None:
        if self._project is None or self._current_image is None:
            QMessageBox.information(
                self, "Нет изображения", "Открой задачу с изображением."
            )
            return
        models_dir = app_root() / "models"
        if not models_dir.exists():
            QMessageBox.warning(
                self,
                "Нет папки models",
                f"Папка не найдена: {models_dir}",
            )
            return
        model_files = sorted(models_dir.glob("*.pt"))
        if not model_files:
            QMessageBox.warning(
                self,
                "Нет моделей",
                f"В папке {models_dir} нет .pt файлов.",
            )
            return
        labels = self._project.repo.list_labels()
        available = [l for l in labels if l.id != 0]
        if not available:
            QMessageBox.warning(
                self, "Нет классов", "Сначала создай хотя бы один класс."
            )
            return
        from src.annotator.ai.yolo_inference import YoloInference, has_cuda
        cuda_available = has_cuda()
        dialog = AiDialog(self, model_files, labels, cuda_available)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        model_path = dialog.selected_model_path()
        label_id = dialog.selected_label_id()
        conf = dialog.confidence()
        use_gpu = dialog.use_gpu()
        batch = dialog.batch_mode()
        if model_path is None or label_id is None:
            return
        device = "0" if use_gpu else "cpu"
        if batch:
            self._run_ai_batch(model_path, label_id, conf, device)
        else:
            self._run_ai_single(model_path, label_id, conf, device, use_gpu)

    def _run_ai_single(
        self,
        model_path: "Path",
        label_id: int,
        conf: float,
        device: str,
        use_gpu: bool,
    ) -> None:
        if self._current_image is None:
            return
        shape = self._image_shape(self._current_image)
        if shape is None:
            return
        progress = AiProgressDialog(self, model_path.name, use_gpu)
        progress.show()
        QApplication.processEvents()
        polygons: list[list[tuple[float, float]]] = []
        try:
            from src.annotator.ai.yolo_inference import YoloInference
            inf = YoloInference.get(model_path)
            QApplication.processEvents()
            polygons = inf.predict(
                self._current_image.source_path,
                conf=conf,
                device=device,
            )
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Ошибка инференса", f"{e}")
            return
        progress.close()
        if not polygons:
            QMessageBox.information(
                self, "Готово", "Модель не нашла объектов на этом изображении."
            )
            return
        commands: list[Command] = []
        last_instance_id: int | None = None
        for poly in polygons:
            result = self._create_polygon_instance(poly, label_id, shape)
            if result is None:
                continue
            instance_id, created_at = result
            last_instance_id = instance_id
            _lid, mask = self._current_instances[instance_id]
            commands.append(CreateInstanceCommand(
                self,
                instance_id,
                self._current_image.id,
                label_id,
                mask.copy(),
                created_at,
            ))
        if not commands:
            return
        self._ensure_image_annotated(True)
        self.canvas.set_instances(
            self._current_instances, self._visible_instances
        )
        self._refresh_objects_panel()
        if last_instance_id is not None:
            self.objects_panel.set_selected_instance_id(last_instance_id)
        self._push_commands(commands)

    def _run_ai_batch(
        self,
        model_path: "Path",
        label_id: int,
        conf: float,
        device: str,
    ) -> None:
        if self._project is None or self._task_id is None:
            return
        all_images = self._project.repo.list_images_for_task(self._task_id)
        targets = [img for img in all_images if not img.is_annotated]
        if not targets:
            QMessageBox.information(
                self,
                "Нечего обрабатывать",
                "В задаче нет неразмеченных изображений.",
            )
            return
        progress = QProgressDialog(
            f"AI: 0 / {len(targets)}", "Отмена", 0, len(targets), self
        )
        progress.setWindowTitle("Batch AI разметка")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setValue(0)
        QApplication.processEvents()

        try:
            from src.annotator.ai.yolo_inference import YoloInference
            inf = YoloInference.get(model_path)
        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self, "Ошибка загрузки модели", f"{e}"
            )
            return

        processed_ids: set[int] = set()
        instances_created = 0
        cancelled = False
        for i, img in enumerate(targets):
            if progress.wasCanceled():
                cancelled = True
                break
            progress.setLabelText(
                f"AI: {i + 1} / {len(targets)} — {img.filename}"
            )
            shape = self._image_shape(img)
            if shape is None:
                progress.setValue(i + 1)
                QApplication.processEvents()
                continue
            try:
                polygons = inf.predict(
                    img.source_path, conf=conf, device=device
                )
            except Exception:
                polygons = []
            if polygons:
                hist = self._histories.setdefault(img.id, CommandHistory())
                batch_commands: list[Command] = []
                for poly in polygons:
                    result = self._ai_create_instance_for_image(
                        img.id, label_id, poly, shape
                    )
                    if result is None:
                        continue
                    iid, ca, mask = result
                    instances_created += 1
                    batch_commands.append(CreateInstanceCommand(
                        self, iid, img.id, label_id, mask.copy(), ca
                    ))
                if batch_commands:
                    if len(batch_commands) == 1:
                        hist.push(batch_commands[0])
                    else:
                        hist.push(CompositeCommand(batch_commands))
                    self._project.repo.update_image_annotated(img.id, True)
                    processed_ids.add(img.id)
            progress.setValue(i + 1)
            QApplication.processEvents()
        progress.close()

        if (
            self._current_image is not None
            and self._current_image.id in processed_ids
        ):
            fresh = self._project.repo.get_image(self._current_image.id)
            if fresh is not None:
                self._current_image = fresh
            self._load_instances_for_current()
        self.image_list.refresh_thumbnails()

        msg = (
            f"Обработано {len(processed_ids)} изображений, "
            f"создано {instances_created} объектов."
        )
        if cancelled:
            msg = "Прервано пользователем.\n" + msg
        QMessageBox.information(self, "Готово", msg)

    def _ai_create_instance_for_image(
        self,
        image_id: int,
        label_id: int,
        points: list,
        shape: tuple[int, int],
    ) -> tuple[int, str, np.ndarray] | None:
        if self._project is None or len(points) < 3:
            return None
        instance_id, created_at = self._project.repo.create_instance(
            image_id, label_id
        )
        mask = np.zeros(shape, dtype=np.uint8)
        pts = np.array(
            [[int(round(x)), int(round(y))] for x, y in points], dtype=np.int32
        )
        cv2.fillPoly(mask, [pts], 1)
        filename = instance_mask_filename(image_id, instance_id)
        try:
            save_binary_mask(self._project.masks_dir / filename, mask)
        except Exception:
            self._project.repo.delete_instance(instance_id)
            return None
        return instance_id, created_at, mask

    def _handle_polygon_erase(self, points: list) -> None:
        if self._project is None or self._current_image is None:
            return
        if len(points) < 3:
            return
        selected_id = self.objects_panel.selected_instance_id()
        if selected_id is not None and selected_id in self._current_instances:
            targets = [selected_id]
        else:
            targets = list(self._visible_instances)
        if not targets:
            return
        pts = np.array(
            [[int(round(x)), int(round(y))] for x, y in points], dtype=np.int32
        )
        commands: list[Command] = []
        for iid in targets:
            if iid not in self._current_instances:
                continue
            _lid, mask = self._current_instances[iid]
            before = mask.copy()
            cv2.fillPoly(mask, [pts], 0)
            if not mask.any():
                record = self._project.repo.get_instance(iid)
                created_iso = (
                    record.created_at.isoformat() if record else ""
                )
                lbl_id = record.label_id if record else _lid
                commands.append(DeleteInstanceCommand(
                    self, iid, self._current_image.id,
                    lbl_id, before, created_iso,
                ))
                filename = instance_mask_filename(self._current_image.id, iid)
                delete_mask_file(self._project.masks_dir / filename)
                self._project.repo.delete_instance(iid)
                self._current_instances.pop(iid, None)
                self._visible_instances.discard(iid)
            else:
                diff = mask != before
                if diff.any():
                    ys, xs = np.where(diff)
                    y1, y2 = int(ys.min()), int(ys.max()) + 1
                    x1, x2 = int(xs.min()), int(xs.max()) + 1
                    commands.append(ModifyMaskCommand(
                        self, iid, self._current_image.id,
                        (y1, y2, x1, x2),
                        before[y1:y2, x1:x2].copy(),
                        mask[y1:y2, x1:x2].copy(),
                    ))
                self._save_instance_mask(iid)
        still_has = self._project.repo.image_has_instances(self._current_image.id)
        self._ensure_image_annotated(still_has)
        self.canvas.set_instances(
            self._current_instances, self._visible_instances
        )
        self._refresh_objects_panel()
        self._push_commands(commands)

    def _on_brush_pressed(self, scene_pt: QPointF) -> None:
        if self._project is None or self._current_image is None:
            return
        tool = self.canvas.current_tool()
        shape = self._image_shape(self._current_image)
        if shape is None:
            return
        self._stroke_snapshots = {}
        self._stroke_new_instances = {}
        self._brush_modified_instances = set()
        if tool == Tool.BRUSH:
            selected_id = self.objects_panel.selected_instance_id()
            if (
                selected_id is not None
                and selected_id in self._current_instances
            ):
                self._brush_target_instance = selected_id
                self._brush_modified_instances.add(selected_id)
                _lid, mask = self._current_instances[selected_id]
                self._stroke_snapshots[selected_id] = mask.copy()
            else:
                if self._active_label is None or self._active_label.id == 0:
                    QMessageBox.information(
                        self,
                        "Нет активного класса",
                        "Выбери класс в выпадающем списке сверху "
                        "или объект на вкладке «Объекты».",
                    )
                    return
                instance_id, created_at = self._project.repo.create_instance(
                    self._current_image.id, self._active_label.id
                )
                mask = np.zeros(shape, dtype=np.uint8)
                self._current_instances[instance_id] = (
                    self._active_label.id,
                    mask,
                )
                self._visible_instances.add(instance_id)
                self._brush_target_instance = instance_id
                self._brush_modified_instances.add(instance_id)
                self._stroke_new_instances[instance_id] = created_at
            self._paint_segment(scene_pt, scene_pt, value=1)
            self._schedule_brush_refresh()
        elif tool == Tool.ERASER:
            selected_id = self.objects_panel.selected_instance_id()
            if (
                selected_id is not None
                and selected_id in self._current_instances
            ):
                self._brush_target_instance = selected_id
                self._brush_modified_instances.add(selected_id)
                self._eraser_all_mode = False
                _lid, mask = self._current_instances[selected_id]
                self._stroke_snapshots[selected_id] = mask.copy()
            else:
                self._brush_target_instance = None
                self._eraser_all_mode = True
            self._erase_segment(scene_pt, scene_pt)
            self._schedule_brush_refresh()

    def _on_brush_moved(self, p1: QPointF, p2: QPointF) -> None:
        tool = self.canvas.current_tool()
        if tool == Tool.BRUSH:
            if self._brush_target_instance is None:
                return
            self._paint_segment(p1, p2, value=1)
            self._schedule_brush_refresh()
        elif tool == Tool.ERASER:
            if not self._eraser_all_mode and self._brush_target_instance is None:
                return
            self._erase_segment(p1, p2)
            self._schedule_brush_refresh()

    def _on_brush_released(self) -> None:
        tool = self.canvas.current_tool()
        self._brush_target_instance = None
        self._eraser_all_mode = False
        self._do_brush_refresh()
        if tool == Tool.BRUSH:
            commands = self._build_brush_stroke_commands()
            for iid in list(self._brush_modified_instances):
                if iid in self._current_instances:
                    self._save_instance_mask(iid)
            self._ensure_image_annotated(True)
            self._refresh_objects_panel()
            self._push_commands(commands)
        elif tool == Tool.ERASER:
            commands = self._build_eraser_stroke_commands()
            for iid in list(self._brush_modified_instances):
                if iid not in self._current_instances:
                    continue
                _lid, mask = self._current_instances[iid]
                if not mask.any():
                    self._delete_empty_instance(iid)
                else:
                    self._save_instance_mask(iid)
            if self._project is not None and self._current_image is not None:
                still_has = self._project.repo.image_has_instances(
                    self._current_image.id
                )
                self._ensure_image_annotated(still_has)
            self._refresh_objects_panel()
            self._push_commands(commands)
        self._brush_modified_instances.clear()
        self._stroke_snapshots.clear()
        self._stroke_new_instances.clear()

    def _build_brush_stroke_commands(self) -> list[Command]:
        commands: list[Command] = []
        if self._current_image is None:
            return commands
        for iid in self._brush_modified_instances:
            if iid in self._stroke_new_instances:
                if iid in self._current_instances:
                    lid, mask = self._current_instances[iid]
                    if mask.any():
                        commands.append(CreateInstanceCommand(
                            self, iid, self._current_image.id, lid,
                            mask.copy(), self._stroke_new_instances[iid],
                        ))
            elif iid in self._stroke_snapshots:
                if iid in self._current_instances:
                    _lid, mask = self._current_instances[iid]
                    before = self._stroke_snapshots[iid]
                    cmd = self._make_modify_command(iid, before, mask)
                    if cmd is not None:
                        commands.append(cmd)
        return commands

    def _build_eraser_stroke_commands(self) -> list[Command]:
        commands: list[Command] = []
        if self._project is None or self._current_image is None:
            return commands
        for iid in list(self._brush_modified_instances):
            if iid not in self._stroke_snapshots:
                continue
            before = self._stroke_snapshots[iid]
            if iid not in self._current_instances:
                continue
            _lid, mask = self._current_instances[iid]
            if not mask.any():
                record = self._project.repo.get_instance(iid)
                if record is not None:
                    commands.append(DeleteInstanceCommand(
                        self, iid, self._current_image.id,
                        record.label_id, before,
                        record.created_at.isoformat(),
                    ))
            else:
                cmd = self._make_modify_command(iid, before, mask)
                if cmd is not None:
                    commands.append(cmd)
        return commands

    def _make_modify_command(
        self, iid: int, before: np.ndarray, after: np.ndarray
    ) -> ModifyMaskCommand | None:
        if self._current_image is None:
            return None
        diff = before != after
        if not diff.any():
            return None
        ys, xs = np.where(diff)
        y1, y2 = int(ys.min()), int(ys.max()) + 1
        x1, x2 = int(xs.min()), int(xs.max()) + 1
        return ModifyMaskCommand(
            self, iid, self._current_image.id, (y1, y2, x1, x2),
            before[y1:y2, x1:x2].copy(),
            after[y1:y2, x1:x2].copy(),
        )

    def _paint_segment(self, p1: QPointF, p2: QPointF, value: int) -> None:
        if self._brush_target_instance is None:
            return
        target = self._current_instances.get(self._brush_target_instance)
        if target is None:
            return
        _lid, mask = target
        x1, y1 = int(round(p1.x())), int(round(p1.y()))
        x2, y2 = int(round(p2.x())), int(round(p2.y()))
        cv2.line(mask, (x1, y1), (x2, y2), value, thickness=self._brush_size)

    def _erase_segment(self, p1: QPointF, p2: QPointF) -> None:
        x1, y1 = int(round(p1.x())), int(round(p1.y()))
        x2, y2 = int(round(p2.x())), int(round(p2.y()))
        if self._eraser_all_mode:
            for iid in list(self._visible_instances):
                if iid not in self._current_instances:
                    continue
                _lid, mask = self._current_instances[iid]
                if iid not in self._stroke_snapshots:
                    self._stroke_snapshots[iid] = mask.copy()
                cv2.line(
                    mask, (x1, y1), (x2, y2), 0, thickness=self._brush_size
                )
                self._brush_modified_instances.add(iid)
        else:
            self._paint_segment(p1, p2, 0)

    def _schedule_brush_refresh(self) -> None:
        if self._brush_refresh_pending:
            return
        self._brush_refresh_pending = True
        self._brush_paint_timer.start()

    def _do_brush_refresh(self) -> None:
        self._brush_refresh_pending = False
        self.canvas.set_instances(
            self._current_instances, self._visible_instances
        )

    def _save_instance_mask(self, instance_id: int) -> None:
        if (
            self._project is None
            or self._current_image is None
            or instance_id not in self._current_instances
        ):
            return
        _lid, mask = self._current_instances[instance_id]
        filename = instance_mask_filename(self._current_image.id, instance_id)
        path = self._project.masks_dir / filename
        try:
            save_binary_mask(path, mask)
        except Exception:
            return

    def _delete_empty_instance(self, instance_id: int) -> None:
        if self._project is None or self._current_image is None:
            return
        filename = instance_mask_filename(self._current_image.id, instance_id)
        delete_mask_file(self._project.masks_dir / filename)
        self._project.repo.delete_instance(instance_id)
        self._current_instances.pop(instance_id, None)
        self._visible_instances.discard(instance_id)

    def _on_object_visibility(self, instance_id: int, visible: bool) -> None:
        if visible:
            self._visible_instances.add(instance_id)
        else:
            self._visible_instances.discard(instance_id)
        self.canvas.set_visible_instances(self._visible_instances)

    def _on_object_delete(self, instance_id: int) -> None:
        if self._project is None or self._current_image is None:
            return
        record = self._project.repo.get_instance(instance_id)
        if record is None or instance_id not in self._current_instances:
            return
        _lid, mask = self._current_instances[instance_id]
        cmd = DeleteInstanceCommand(
            self, instance_id, self._current_image.id,
            record.label_id, mask.copy(), record.created_at.isoformat(),
        )
        filename = instance_mask_filename(self._current_image.id, instance_id)
        delete_mask_file(self._project.masks_dir / filename)
        self._project.repo.delete_instance(instance_id)
        self._current_instances.pop(instance_id, None)
        self._visible_instances.discard(instance_id)
        still_has = self._project.repo.image_has_instances(
            self._current_image.id
        )
        self._ensure_image_annotated(still_has)
        self.canvas.set_instances(
            self._current_instances, self._visible_instances
        )
        self._refresh_objects_panel()
        self._push_command(cmd)

    def _on_object_change_class(
        self, instance_id: int, new_label_id: int
    ) -> None:
        if self._project is None:
            return
        old_label_id: int | None = None
        if instance_id in self._current_instances:
            old_label_id = self._current_instances[instance_id][0]
        else:
            record = self._project.repo.get_instance(instance_id)
            if record is not None:
                old_label_id = record.label_id
        self._project.repo.update_instance_label(instance_id, new_label_id)
        if instance_id in self._current_instances:
            _old_lid, mask = self._current_instances[instance_id]
            self._current_instances[instance_id] = (new_label_id, mask)
        self.canvas.set_instances(
            self._current_instances, self._visible_instances
        )
        self._refresh_objects_panel()
        self._push_command(ChangeClassCommand(
            self, instance_id, old_label_id, new_label_id,
        ))

    def _update_nav_buttons(self) -> None:
        has = self._total > 0
        at_first = self._current_row <= 0
        at_last = self._current_row < 0 or self._current_row >= self._total - 1
        self.first_btn.setEnabled(has and not at_first)
        self.prev_btn.setEnabled(has and not at_first)
        self.next_btn.setEnabled(has and not at_last)
        self.last_btn.setEnabled(has and not at_last)
        self.slider.setEnabled(has)
        self.spinbox.setEnabled(has)

    def _on_image_selected(self, image: Image, row: int) -> None:
        if self._updating:
            return
        self._set_position(row)

    def _on_slider_changed(self, value: int) -> None:
        if self._updating:
            return
        self._set_position(value - 1)

    def _on_spinbox_changed(self, value: int) -> None:
        if self._updating:
            return
        self._set_position(value - 1)
