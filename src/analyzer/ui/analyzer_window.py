from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, List

import numpy as np

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.analyzer.ai.inference_worker import InferenceWorker
from src.analyzer.core.data_models import ImageResult
from src.analyzer.core.preprocessing import (
    apply_preprocessing, apply_frangi_filter, ensure_bgr,
    compute_laplacian_variance,
)
from src.analyzer.core.vessel_analysis import compute_vessel_metrics, build_overlay
from src.analyzer.ui.metrics_panel import MetricsPanel
from src.analyzer.ui.preprocess_panel import PreprocessPanel
from src.analyzer.ui.report_dialog import ReportDialog
from src.analyzer.ui.viewer import ImageViewer
from src.analyzer.ui.mask_editor import MaskEditorDialog
from src.shared.constants import (
    ANALYZER_CLASS_NAMES, ANALYZER_QUALITY_THRESHOLD_DEFAULT,
    SUPPORTED_IMAGE_EXTENSIONS,
)
from skimage.morphology import skeletonize
import cv2


class AnalyzerWindow(QWidget):
    """Вкладка «Анализ» — полный QCA-анализатор ангиограмм."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._results: List[ImageResult] = []
        self._current_result: Optional[ImageResult] = None
        self._current_class_idx: int = 0
        self._worker: Optional[InferenceWorker] = None
        self._model_path: str = ""
        self._build_ui()

    # ── Построение интерфейса ────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Левая панель ──────────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(310)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        grp_model = QGroupBox("Модель YOLO")
        gm = QVBoxLayout(grp_model)
        self.lbl_model = QLabel("Не выбрана")
        self.lbl_model.setWordWrap(True)
        self.lbl_model.setStyleSheet("color: #8b949e; font-size: 11px;")
        btn_model = QPushButton("Выбрать .pt файл")
        btn_model.clicked.connect(self._load_model)
        gm.addWidget(self.lbl_model)
        gm.addWidget(btn_model)
        left_lay.addWidget(grp_model)

        grp_img = QGroupBox("Изображения")
        gi = QVBoxLayout(grp_img)
        h = QHBoxLayout()
        btn_files  = QPushButton("Добавить файлы")
        btn_folder = QPushButton("Добавить папку")
        btn_clear  = QPushButton("Очистить")
        btn_files.clicked.connect(self._load_images)
        btn_folder.clicked.connect(self._load_folder)
        btn_clear.clicked.connect(self._clear_images)
        h.addWidget(btn_files)
        h.addWidget(btn_folder)
        gi.addLayout(h)
        gi.addWidget(btn_clear)
        self.lbl_img_count = QLabel("Файлов: 0")
        self.lbl_img_count.setStyleSheet("color: #8b949e;")
        gi.addWidget(self.lbl_img_count)
        left_lay.addWidget(grp_img)

        grp_list = QGroupBox("Список файлов")
        gl = QVBoxLayout(grp_list)
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels(["Файл", "Статус", "σ²Lap"])
        self.file_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.file_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.file_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.file_table.currentCellChanged.connect(self._on_file_selected)
        gl.addWidget(self.file_table)
        left_lay.addWidget(grp_list, 1)

        grp_qual = QGroupBox("Качество кадра")
        gq = QHBoxLayout(grp_qual)
        gq.addWidget(QLabel("Порог σ²Lap:"))
        self.spin_quality = QDoubleSpinBox()
        self.spin_quality.setRange(0, 5000)
        self.spin_quality.setValue(ANALYZER_QUALITY_THRESHOLD_DEFAULT)
        self.spin_quality.setFixedWidth(80)
        gq.addWidget(self.spin_quality)
        gq.addStretch()
        left_lay.addWidget(grp_qual)

        grp_scale = QGroupBox("Масштаб")
        gs = QHBoxLayout(grp_scale)
        gs.addWidget(QLabel("мм/пиксель:"))
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(0.001, 100.0)
        self.spin_scale.setValue(1.0)
        self.spin_scale.setDecimals(4)
        self.spin_scale.setFixedWidth(90)
        gs.addWidget(self.spin_scale)
        gs.addStretch()
        left_lay.addWidget(grp_scale)

        root.addWidget(left)

        # ── Центральная область ───────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)

        view_bar = QHBoxLayout()
        self.combo_view = QComboBox()
        self.combo_view.addItems([
            "Оригинал", "Предобработанное",
            "Overlay (маски+скелет)", "Vesselness",
        ])
        self.combo_view.currentIndexChanged.connect(self._refresh_view)
        self.combo_class = QComboBox()
        self.combo_class.addItems(list(ANALYZER_CLASS_NAMES.values()))
        self.combo_class.currentIndexChanged.connect(self._on_class_changed)
        btn_zoom_reset = QPushButton("1:1")
        btn_zoom_reset.setFixedWidth(40)
        btn_zoom_reset.clicked.connect(lambda: self.viewer.reset_zoom())
        view_bar.addWidget(QLabel("Вид:"))
        view_bar.addWidget(self.combo_view)
        view_bar.addSpacing(12)
        view_bar.addWidget(QLabel("Класс:"))
        view_bar.addWidget(self.combo_class)
        view_bar.addWidget(btn_zoom_reset)
        view_bar.addStretch()
        center_lay.addLayout(view_bar)

        self.viewer = ImageViewer()
        center_lay.addWidget(self.viewer, 1)

        self.preproc_panel = PreprocessPanel()
        self.preproc_panel.changed.connect(self._on_preproc_changed)
        center_lay.addWidget(self.preproc_panel)
        splitter.addWidget(center)

        # ── Правая панель ─────────────────────────────────────────────────
        right = QWidget()
        right.setFixedWidth(340)
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)

        grp_metrics = QGroupBox("QCA-метрики")
        gmet = QVBoxLayout(grp_metrics)
        self.metrics_panel = MetricsPanel()
        gmet.addWidget(self.metrics_panel)
        right_lay.addWidget(grp_metrics, 1)

        grp_run = QGroupBox("Запуск")
        gr = QVBoxLayout(grp_run)
        self.btn_run_single = QPushButton("▶  Анализировать текущее")
        self.btn_run_batch  = QPushButton("⚡  Пакетный анализ (все)")
        self.btn_cancel     = QPushButton("✕  Отмена")
        self.btn_edit_mask  = QPushButton("✏  Редактировать маску")
        self.btn_report     = QPushButton("📊  Сводный отчёт")
        self.btn_cancel.setEnabled(False)
        self.btn_edit_mask.setEnabled(False)
        self.btn_report.setEnabled(False)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.lbl_progress = QLabel("")
        self.lbl_progress.setStyleSheet("color: #8b949e; font-size: 11px;")
        for w in (self.btn_run_single, self.btn_run_batch, self.btn_cancel,
                  self.progress, self.lbl_progress, self.btn_edit_mask,
                  self.btn_report):
            gr.addWidget(w)
        right_lay.addWidget(grp_run)
        splitter.addWidget(right)
        splitter.setSizes([860, 340])
        root.addWidget(splitter, 1)

        self.btn_run_single.clicked.connect(self._run_single)
        self.btn_run_batch.clicked.connect(self._run_batch)
        self.btn_cancel.clicked.connect(self._cancel_worker)
        self.btn_edit_mask.clicked.connect(self._edit_mask)
        self.btn_report.clicked.connect(self._open_report)

    # ── Слоты — файлы ────────────────────────────────────────────────────
    def _load_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать модель YOLO", "", "PyTorch Model (*.pt);;All (*.*)"
        )
        if path:
            self._model_path = path
            self.lbl_model.setText(os.path.basename(path))
            self.lbl_model.setStyleSheet("color: #3fb950; font-size: 11px;")

    def _load_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Выбрать изображения", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.tiff *.tif)",
        )
        if paths:
            self._add_paths(paths)

    def _load_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Выбрать папку с изображениями"
        )
        if folder:
            paths = []
            for ext in SUPPORTED_IMAGE_EXTENSIONS:
                paths.extend(str(p) for p in Path(folder).rglob(f"*{ext}"))
            if paths:
                self._add_paths(sorted(paths))

    def _add_paths(self, paths: List[str]) -> None:
        existing = {r.path for r in self._results}
        added = 0
        for p in paths:
            if p not in existing:
                self._results.append(ImageResult(path=p, name=os.path.basename(p)))
                added += 1
        self._refresh_file_table()

    def _clear_images(self) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Внимание", "Остановите анализ перед очисткой.")
            return
        self._results.clear()
        self._current_result = None
        self.file_table.setRowCount(0)
        self.viewer.set_image_bgr(None)
        self.metrics_panel.clear_metrics()
        self.lbl_img_count.setText("Файлов: 0")
        self.btn_report.setEnabled(False)
        self.btn_edit_mask.setEnabled(False)

    def _refresh_file_table(self) -> None:
        self.file_table.setRowCount(len(self._results))
        for i, r in enumerate(self._results):
            status, color = "Ожидание", "#8b949e"
            if r.error:
                status, color = "Ошибка", "#f85149"
            elif r.skipped_quality:
                status, color = "Пропущен(кач.)", "#f0883e"
            elif r.metrics:
                if getattr(r, "edited", False):
                    status, color = "Готово ✎", "#3fb950"
                else:
                    status, color = "Готово", "#3fb950"
            elif r.loaded:
                status, color = "Загружен", "#58a6ff"
            self.file_table.setItem(i, 0, QTableWidgetItem(r.name))
            st = QTableWidgetItem(status)
            st.setForeground(QColor(color))
            self.file_table.setItem(i, 1, st)
            lv = QTableWidgetItem(f"{r.laplacian_var:.1f}" if r.laplacian_var else "—")
            self.file_table.setItem(i, 2, lv)
        self.lbl_img_count.setText(f"Файлов: {len(self._results)}")
        if any(r.metrics for r in self._results):
            self.btn_report.setEnabled(True)

    def _on_file_selected(self, row, col, prev_row, prev_col) -> None:
        if row < 0 or row >= len(self._results):
            return
        self._current_result = self._results[row]
        self._refresh_view()
        self._show_current_metrics()
        self._update_edit_button()

    def _on_class_changed(self, idx: int) -> None:
        self._current_class_idx = idx
        self._show_current_metrics()

    def _on_preproc_changed(self) -> None:
        self._refresh_view()

    def _refresh_view(self) -> None:
        r = self._current_result
        if r is None:
            return
        pp   = self.preproc_panel.get_params()
        mode = self.combo_view.currentIndex()

        if mode == 0:
            img = r.original
        elif mode == 1:
            src = r.preprocessed if r.preprocessed is not None else r.original
            img = src
        elif mode == 2:
            img = r.overlay if r.overlay is not None else r.original
        elif mode == 3:
            src = r.preprocessed if r.preprocessed is not None else r.original
            img = apply_frangi_filter(src) if src is not None else None
        else:
            img = r.original

        if img is not None and mode in (0, 1):
            img = apply_preprocessing(img, pp)

        self.viewer.set_image_bgr(img)

    def _show_current_metrics(self) -> None:
        r = self._current_result
        if r is None or not r.metrics:
            self.metrics_panel.clear_metrics()
            return
        m = next((x for x in r.metrics if x.class_id == self._current_class_idx), None)
        if m is None:
            m = r.metrics[0]
        self.metrics_panel.show_metrics(m, laplacian=r.laplacian_var)

    def _update_edit_button(self) -> None:
        """Кнопка правки доступна, если у текущего кадра есть маска."""
        r = self._current_result
        self.btn_edit_mask.setEnabled(bool(r and r.masks))

    # ── Слоты — запуск ───────────────────────────────────────────────────
    def _run_single(self) -> None:
        if self._current_result is None:
            QMessageBox.warning(self, "Нет выбора", "Выберите файл в списке.")
            return
        r = self._current_result
        if not r.loaded:
            img = cv2.imread(r.path)
            if img is None:
                r.error = "Не удалось загрузить"
                self._refresh_file_table()
                return
            r.original = ensure_bgr(img)
            import cv2 as _cv2
            gray = _cv2.cvtColor(img, _cv2.COLOR_BGR2GRAY)
            r.laplacian_var = compute_laplacian_variance(gray)
            r.loaded = True
        self._refresh_view()
        if not self._model_path:
            QMessageBox.warning(self, "Модель не выбрана",
                                "Укажите файл .pt в панели «Модель YOLO».")
            return
        self._start_batch([r.path])

    def _run_batch(self) -> None:
        if not self._results:
            QMessageBox.warning(self, "Нет файлов", "Сначала загрузите изображения.")
            return
        if not self._model_path:
            QMessageBox.warning(self, "Модель не выбрана",
                                "Укажите файл .pt в панели «Модель YOLO».")
            return
        self._start_batch([r.path for r in self._results])

    def _start_batch(self, paths: List[str]) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Занято", "Анализ уже выполняется.")
            return
        self._worker = InferenceWorker(
            image_paths=paths,
            model_path=self._model_path,
            preproc_params=self.preproc_panel.get_params(),
            quality_threshold=self.spin_quality.value(),
            scale_mm_per_px=self.spin_scale.value(),
        )
        self._worker.signals.progress.connect(self._on_progress)
        self._worker.signals.result.connect(self._on_result)
        self._worker.signals.finished.connect(self._on_finished)
        self._worker.signals.error.connect(self._on_error)
        self.progress.setRange(0, len(paths))
        self.progress.setValue(0)
        self.btn_cancel.setEnabled(True)
        self.btn_run_batch.setEnabled(False)
        self.btn_run_single.setEnabled(False)
        self._worker.start()

    def _cancel_worker(self) -> None:
        if self._worker:
            self._worker.cancel()

    @Slot(int, int, str)
    def _on_progress(self, cur: int, total: int, name: str) -> None:
        self.progress.setValue(cur)
        self.lbl_progress.setText(f"{cur}/{total}: {name}")

    @Slot(object)
    def _on_result(self, res: ImageResult) -> None:
        for i, r in enumerate(self._results):
            if r.path == res.path:
                self._results[i] = res
                if self._current_result and self._current_result.path == res.path:
                    self._current_result = res
                break
        self._refresh_file_table()
        if self._current_result and self._current_result.path == res.path:
            self._refresh_view()
            self._show_current_metrics()
            self._update_edit_button()

    @Slot()
    def _on_finished(self) -> None:
        self.btn_cancel.setEnabled(False)
        self.btn_run_batch.setEnabled(True)
        self.btn_run_single.setEnabled(True)
        done = sum(1 for r in self._results if r.metrics)
        self.lbl_progress.setText(f"Готово. Обработано: {done}/{len(self._results)}")
        if done > 0:
            self.btn_report.setEnabled(True)
        self._update_edit_button()

    @Slot(str)
    def _on_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Ошибка анализа", msg)
        self._on_finished()

    def _open_report(self) -> None:
        ReportDialog(self._results, parent=self).exec()

    # ── Ручная правка маски YOLO ─────────────────────────────────────────
    def _edit_mask(self) -> None:
        """Открыть редактор для ручной корректировки маски текущего кадра."""
        r = self._current_result
        if r is None or not r.masks:
            QMessageBox.information(
                self, "Нет маски",
                "Сначала выполните анализ кадра, чтобы получить маску YOLO для правки."
            )
            return

        base = r.preprocessed if r.preprocessed is not None else r.original
        if base is None:
            img = cv2.imread(r.path)
            base = ensure_bgr(img) if img is not None else None
        if base is None:
            QMessageBox.warning(self, "Ошибка", "Не удалось загрузить изображение кадра.")
            return

        dlg = MaskEditorDialog(base, r.masks, parent=self)
        if not dlg.exec():
            return

        r.masks = dlg.result_masks
        self._recompute_after_edit(r)
        self._refresh_file_table()
        self.combo_view.setCurrentIndex(2)   # показать overlay с правкой
        self._refresh_view()
        self._show_current_metrics()
        self._update_edit_button()
        self.lbl_progress.setText(f"Маска кадра «{r.name}» исправлена вручную, метрики пересчитаны.")

    def _recompute_after_edit(self, r: ImageResult) -> None:
        """Пересчитать скелет, QCA-метрики и overlay по исправленной маске."""
        proc = r.preprocessed if r.preprocessed is not None else r.original
        scale = self.spin_scale.value()
        r.skeletons = {}
        r.metrics = []
        for cls_id in sorted(r.masks.keys()):
            mask_bin = r.masks[cls_id]
            if int((mask_bin > 0).sum()) < 10:
                continue
            skel = skeletonize(mask_bin > 0)
            r.skeletons[cls_id] = skel.astype(np.uint8) * 255
            m = compute_vessel_metrics(
                mask_bin, cls_id, r.name, r.path, scale
            )
            m.laplacian_var = r.laplacian_var
            m.quality_ok = True
            r.metrics.append(m)
        if proc is not None and r.masks:
            r.overlay = build_overlay(proc, r.masks, r.skeletons)
        elif proc is not None:
            r.overlay = proc.copy()
        r.edited = True
