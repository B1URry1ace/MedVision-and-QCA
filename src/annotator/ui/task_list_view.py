#task_list_view.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.annotator.core.i18n import tr
from src.annotator.core.project import Project
from src.annotator.io.seg_mask_exporter import ExportCancelled, export_task
from src.annotator.io.thumbnail_worker import ThumbnailWorker
from src.annotator.ui.classes_panel import ClassesPanel
from src.annotator.ui.project_card import TaskCard, TaskCardData


class _ExportOptionsDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        annotated_count: int,
        total_count: int,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Параметры экспорта")
        self.setModal(True)
        layout = QVBoxLayout(self)
        info = QLabel(
            f"Будет экспортировано {annotated_count} размеченных изображений "
            f"из {total_count}."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        self.copy_originals_cb = QCheckBox(
            "Копировать исходные PNG в JPEGImages/"
        )
        self.copy_originals_cb.setChecked(True)
        layout.addWidget(self.copy_originals_cb)
        self.include_objects_cb = QCheckBox(
            "Также экспортировать SegmentationObject/ (instance segmentation)"
        )
        self.include_objects_cb.setChecked(True)
        layout.addWidget(self.include_objects_cb)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def copy_originals(self) -> bool:
        return self.copy_originals_cb.isChecked()

    def include_objects(self) -> bool:
        return self.include_objects_cb.isChecked()


class TaskListView(QWidget):
    thumbnail_progress = Signal(int, int)
    task_open_requested = Signal(int, str)
    close_project_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.project: Project | None = None
        self._worker: ThumbnailWorker | None = None
        self._worker_thread: QThread | None = None
        self._build_ui()

    def set_project(self, project: Project | None) -> None:
        self._stop_worker()
        self.project = project
        self.refresh()
        self.classes_panel.set_project(project)
        if project is not None:
            self._start_worker()

    def _build_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        layout = QVBoxLayout(left)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        title = QLabel(tr("Задачи"))
        title.setStyleSheet("font-size: 20pt; font-weight: bold;")
        header_row.addWidget(title)
        header_row.addStretch()
        close_btn = QPushButton(tr("Закрыть проект"))
        close_btn.clicked.connect(self.close_project_requested.emit)
        header_row.addWidget(close_btn)
        layout.addLayout(header_row)

        top_row = QHBoxLayout()
        self.new_task_name_edit = QLineEdit()
        self.new_task_name_edit.setPlaceholderText(tr("Название новой задачи…"))
        self.new_task_name_edit.returnPressed.connect(self._on_new_task)
        top_row.addWidget(self.new_task_name_edit, stretch=1)
        new_btn = QPushButton(tr("+ Создать задачу"))
        new_btn.clicked.connect(self._on_new_task)
        top_row.addWidget(new_btn)
        layout.addLayout(top_row)

        self.empty_label = QLabel(
            tr("Задач пока нет. Нажми «Новая задача», чтобы добавить.")
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #888; padding: 40px;")
        layout.addWidget(self.empty_label, stretch=1)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._cards_host = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_host)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        self._cards_layout.addStretch()
        self.cards_scroll.setWidget(self._cards_host)
        layout.addWidget(self.cards_scroll, stretch=1)

        splitter.addWidget(left)

        self.classes_panel = ClassesPanel()
        splitter.addWidget(self.classes_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([900, 280])
        outer.addWidget(splitter)

    def refresh(self) -> None:
        while self._cards_layout.count() > 0:
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if self.project is None:
            self.empty_label.setVisible(True)
            self.cards_scroll.setVisible(False)
            return
        tasks = self.project.repo.list_tasks()
        has = bool(tasks)
        self.empty_label.setVisible(not has)
        self.cards_scroll.setVisible(has)
        for task in tasks:
            total = self.project.repo.count_images(task.id)
            thumbs = self.project.repo.count_thumbnails(task.id)
            data = TaskCardData(
                task_id=task.id,
                name=task.name,
                image_count=total,
                thumbs_count=thumbs,
                created_at=task.created_at,
            )
            card = TaskCard(data)
            card.open_clicked.connect(
                lambda tid=task.id, nm=task.name: self.task_open_requested.emit(
                    tid, nm
                )
            )
            card.rename_clicked.connect(
                lambda tid=task.id: self._rename_task(tid)
            )
            card.delete_clicked.connect(
                lambda tid=task.id: self._delete_task(tid)
            )
            card.export_clicked.connect(
                lambda tid=task.id: self._export_task(tid)
            )
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()

    def _task_name(self, task_id: int) -> str | None:
        if self.project is None:
            return None
        for t in self.project.repo.list_tasks():
            if t.id == task_id:
                return t.name
        return None

    def _on_new_task(self) -> None:
        if self.project is None:
            return
        name = self.new_task_name_edit.text().strip()
        if not name:
            self.new_task_name_edit.setFocus()
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку с PNG изображениями", str(Path.home())
        )
        if not folder:
            return
        source_dir = Path(folder)
        try:
            png_files = sorted(
                p for p in source_dir.iterdir()
                if p.is_file() and p.suffix.lower() == ".png"
            )
        except OSError as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось прочитать папку:\n{e}")
            return
        if not png_files:
            QMessageBox.warning(
                self, "Нет изображений", "В папке не найдено PNG-файлов."
            )
            return
        try:
            task_id = self.project.repo.create_task(name, str(source_dir))
            self.project.repo.add_images(
                task_id, [(p.name, str(p)) for p in png_files]
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать задачу:\n{e}")
            return
        self.new_task_name_edit.clear()
        self.refresh()
        self._start_worker()

    def _rename_task(self, task_id: int) -> None:
        if self.project is None:
            return
        current_name = self._task_name(task_id)
        if current_name is None:
            return
        new_name, ok = QInputDialog.getText(
            self, tr("Переименовать"), "", text=current_name
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == current_name:
            return
        self.project.repo.rename_task(task_id, new_name)
        self.refresh()

    def _delete_task(self, task_id: int) -> None:
        if self.project is None:
            return
        resp = QMessageBox.question(
            self,
            tr("Удалить"),
            "Задача, её изображения и миниатюры будут удалены.\n"
            "Исходные PNG-файлы не затрагиваются.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        thumbs = self.project.repo.list_thumbnails_for_task(task_id)
        self.project.repo.delete_task(task_id)
        for fn in thumbs:
            try:
                (self.project.thumbnails_dir / fn).unlink()
            except OSError:
                pass
        self.refresh()

    def _export_task(self, task_id: int) -> None:
        if self.project is None:
            return
        task_name = self._task_name(task_id)
        if task_name is None:
            return
        annotated = self.project.repo.count_annotated_images(task_id)
        total = self.project.repo.count_images(task_id)
        if annotated == 0:
            QMessageBox.warning(
                self,
                "Нечего экспортировать",
                "В этой задаче нет размеченных изображений.",
            )
            return
        opts = _ExportOptionsDialog(self, annotated, total)
        if opts.exec() != QDialog.DialogCode.Accepted:
            return
        copy_originals = opts.copy_originals()
        include_objects = opts.include_objects()
        parent_folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку, куда экспортировать задачу",
            str(Path.home()),
        )
        if not parent_folder:
            return
        target = Path(parent_folder) / task_name
        if target.exists():
            try:
                non_empty = any(target.iterdir())
            except OSError:
                non_empty = False
            if non_empty:
                resp = QMessageBox.question(
                    self,
                    "Папка не пуста",
                    f"Папка '{target}' уже содержит файлы. Продолжить?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return

        progress = QProgressDialog(
            f"Экспорт «{task_name}»…", "Отмена", 0, max(1, annotated), self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setValue(0)

        def cb(done: int, total_: int) -> None:
            progress.setMaximum(max(1, total_))
            progress.setValue(done)
            QApplication.processEvents()
            if progress.wasCanceled():
                raise ExportCancelled()

        try:
            written = export_task(
                self.project,
                task_id,
                target,
                only_annotated=True,
                copy_originals=copy_originals,
                include_segmentation_object=include_objects,
                progress_callback=cb,
            )
        except ExportCancelled:
            progress.close()
            QMessageBox.information(self, "Отменено", "Экспорт отменён.")
            return
        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self, "Ошибка экспорта", f"Не удалось экспортировать:\n{e}"
            )
            return
        progress.close()
        QMessageBox.information(
            self,
            "Готово",
            f"Экспортировано {written} изображений в:\n{target}",
        )

    def _start_worker(self) -> None:
        if self.project is None or self._worker_thread is not None:
            return
        if not self.project.repo.has_pending_thumbnails():
            return
        worker = ThumbnailWorker(
            self.project.db_path, self.project.thumbnails_dir
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_worker_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._worker_thread = thread
        thread.start()

    def _stop_worker(self) -> None:
        if self._worker_thread is None:
            return
        if self._worker is not None:
            self._worker.stop()
        self._worker_thread.wait(5000)
        self._worker_thread = None
        self._worker = None

    def _on_progress(self, current: int, total: int) -> None:
        self.thumbnail_progress.emit(current, total)

    def _on_worker_finished(self) -> None:
        self._worker_thread = None
        self._worker = None
        self.refresh()
        self.thumbnail_progress.emit(0, 0)
        if self.project is not None and self.project.repo.has_pending_thumbnails():
            self._start_worker()
