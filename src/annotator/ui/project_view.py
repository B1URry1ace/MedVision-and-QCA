#project_view.py
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from src.annotator.core.project import Project
from src.annotator.ui.task_list_view import TaskListView
from src.annotator.ui.task_workspace import TaskWorkspace


class ProjectViewWidget(QWidget):
    thumbnail_progress = Signal(int, int)
    image_position_changed = Signal(int, int, str)
    close_project_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.task_list = TaskListView()
        self.task_list.thumbnail_progress.connect(self._forward_thumb_progress)
        self.task_list.task_open_requested.connect(self._on_task_open)
        self.task_list.close_project_requested.connect(
            self.close_project_requested.emit
        )
        self.stack.addWidget(self.task_list)

        self.workspace = TaskWorkspace()
        self.workspace.back_requested.connect(self._on_back)
        self.workspace.image_position_changed.connect(
            self.image_position_changed.emit
        )
        self.stack.addWidget(self.workspace)

    def set_project(self, project: Project | None) -> None:
        self._project = project
        self.task_list.set_project(project)
        if project is None:
            self.workspace.clear()
        self.stack.setCurrentWidget(self.task_list)

    def _forward_thumb_progress(self, current: int, total: int) -> None:
        self.thumbnail_progress.emit(current, total)
        if self.stack.currentWidget() is self.workspace:
            self.workspace.refresh_thumbnails()

    def _on_task_open(self, task_id: int, task_name: str) -> None:
        if self._project is None:
            return
        self.workspace.set_task(self._project, task_id, task_name)
        self.stack.setCurrentWidget(self.workspace)

    def _on_back(self) -> None:
        self.workspace.clear()
        self.task_list.refresh()
        self.stack.setCurrentWidget(self.task_list)
