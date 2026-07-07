#project_card.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.annotator.core.i18n import tr


@dataclass
class TaskCardData:
    task_id: int
    name: str
    image_count: int
    thumbs_count: int
    created_at: datetime


class _CardBase(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Card")
        self.setFrameShape(QFrame.Shape.StyledPanel)


class ProjectCard(_CardBase):
    open_clicked = Signal()
    rename_clicked = Signal()
    delete_clicked = Signal()

    def __init__(
        self,
        name: str,
        path: Path,
        image_count: int,
        modified: datetime,
    ) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(8)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; background: transparent;")
        info.addWidget(name_lbl)
        meta_text = (
            f"{tr('Изображений')}: {image_count}   •   "
            f"{tr('Изменён')}: {modified:%Y-%m-%d %H:%M}   •   "
            f"{tr('Папка')}: {path.name}"
        )
        meta_lbl = QLabel(meta_text)
        meta_lbl.setStyleSheet("color: #888; background: transparent;")
        info.addWidget(meta_lbl)
        layout.addLayout(info, stretch=1)

        open_btn = QPushButton(tr("Открыть"))
        open_btn.clicked.connect(self.open_clicked.emit)
        layout.addWidget(open_btn)
        rename_btn = QPushButton(tr("Переименовать"))
        rename_btn.clicked.connect(self.rename_clicked.emit)
        layout.addWidget(rename_btn)
        delete_btn = QPushButton(tr("Удалить"))
        delete_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(delete_btn)


class TaskCard(_CardBase):
    open_clicked = Signal()
    rename_clicked = Signal()
    delete_clicked = Signal()
    export_clicked = Signal()

    def __init__(self, data: TaskCardData) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 12)
        layout.setSpacing(8)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(data.name)
        name_lbl.setStyleSheet("font-size: 13pt; font-weight: bold; background: transparent;")
        info.addWidget(name_lbl)
        stat = f"{tr('Изображений')}: {data.image_count}"
        if data.image_count > 0 and data.thumbs_count < data.image_count:
            stat += (
                f"   •   {tr('Миниатюры')}: "
                f"{data.thumbs_count}/{data.image_count}"
            )
        stat += f"   •   {tr('Создана')}: {data.created_at:%Y-%m-%d %H:%M}"
        meta_lbl = QLabel(stat)
        meta_lbl.setStyleSheet("color: #888; background: transparent;")
        info.addWidget(meta_lbl)
        layout.addLayout(info, stretch=1)

        open_btn = QPushButton(tr("Открыть"))
        open_btn.clicked.connect(self.open_clicked.emit)
        layout.addWidget(open_btn)
        rename_btn = QPushButton(tr("Переименовать"))
        rename_btn.clicked.connect(self.rename_clicked.emit)
        layout.addWidget(rename_btn)
        delete_btn = QPushButton(tr("Удалить"))
        delete_btn.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(delete_btn)
        export_btn = QPushButton(tr("Экспорт…"))
        export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(export_btn)
