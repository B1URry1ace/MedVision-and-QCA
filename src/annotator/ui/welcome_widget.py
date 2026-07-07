#welcome_widget.py
from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.annotator.core.app_paths import projects_dir
from src.annotator.core.i18n import tr
from src.annotator.ui.project_card import ProjectCard


@dataclass
class ProjectSummary:
    path: Path
    name: str
    image_count: int
    modified: datetime


def scan_projects(root: Path) -> list[ProjectSummary]:
    summaries: list[ProjectSummary] = []
    if not root.exists():
        return summaries
    for child in sorted(root.iterdir()):
        db = child / "project.db"
        if not (child.is_dir() and db.exists()):
            continue
        try:
            conn = sqlite3.connect(db)
            try:
                row = conn.execute(
                    "SELECT value FROM meta WHERE key = 'project_name'"
                ).fetchone()
                name = row[0] if row else child.name
                count_row = conn.execute("SELECT COUNT(*) FROM images").fetchone()
                count = count_row[0] if count_row else 0
            finally:
                conn.close()
            mtime = datetime.fromtimestamp(db.stat().st_mtime)
            summaries.append(ProjectSummary(child, name, count, mtime))
        except sqlite3.DatabaseError:
            continue
    summaries.sort(key=lambda s: s.modified, reverse=True)
    return summaries


class WelcomeWidget(QWidget):
    open_requested = Signal(Path)
    new_project_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 32)
        layout.setSpacing(14)

        title = QLabel("Image Annotator")
        title.setStyleSheet("font-size: 26pt; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(tr("Проекты"))
        subtitle.setStyleSheet("font-size: 14pt; color: #888;")
        layout.addWidget(subtitle)

        create_row = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("Название нового проекта…"))
        self.name_input.returnPressed.connect(self._on_create_clicked)
        create_row.addWidget(self.name_input, stretch=1)
        create_btn = QPushButton(tr("+ Создать"))
        create_btn.clicked.connect(self._on_create_clicked)
        create_row.addWidget(create_btn)
        layout.addLayout(create_row)

        self.empty_label = QLabel(
            tr("Проектов пока нет. Введи название и нажми «Создать».")
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

    def focus_name_input(self) -> None:
        self.name_input.setFocus()
        self.name_input.selectAll()

    def _on_create_clicked(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            self.name_input.setFocus()
            return
        self.name_input.clear()
        self.new_project_requested.emit(name)

    def refresh(self) -> None:
        while self._cards_layout.count() > 0:
            item = self._cards_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        summaries = scan_projects(projects_dir())
        has = bool(summaries)
        self.empty_label.setVisible(not has)
        self.cards_scroll.setVisible(has)
        for s in summaries:
            card = ProjectCard(s.name, s.path, s.image_count, s.modified)
            card.open_clicked.connect(
                lambda p=s.path: self.open_requested.emit(p)
            )
            card.rename_clicked.connect(
                lambda p=s.path: self._rename_project(p)
            )
            card.delete_clicked.connect(
                lambda p=s.path: self._delete_project(p)
            )
            self._cards_layout.addWidget(card)
        self._cards_layout.addStretch()

    def _rename_project(self, path: Path) -> None:
        new_name, ok = QInputDialog.getText(
            self, tr("Переименовать"), tr("Переименовать") + ":", text=path.name
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == path.name:
            return
        new_path = path.parent / new_name
        if new_path.exists():
            QMessageBox.warning(
                self, "Error", f"'{new_name}' already exists."
            )
            return
        try:
            path.rename(new_path)
            conn = sqlite3.connect(new_path / "project.db")
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                    ("project_name", new_name),
                )
                conn.commit()
            finally:
                conn.close()
        except (OSError, sqlite3.DatabaseError) as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.refresh()

    def _delete_project(self, path: Path) -> None:
        resp = QMessageBox.question(
            self,
            tr("Удалить"),
            f"{tr('Удалить')} '{path.name}'?\n\n{path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            shutil.rmtree(path)
        except OSError as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.refresh()
