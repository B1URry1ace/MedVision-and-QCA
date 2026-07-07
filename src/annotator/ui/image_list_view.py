#image_list_view.py
from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

from src.annotator.core.models import Image
from src.annotator.core.project import Project


_PLACEHOLDER: QPixmap | None = None


def _placeholder() -> QPixmap:
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        pm = QPixmap(100, 100)
        pm.fill(QColor("#444"))
        _PLACEHOLDER = pm
    return _PLACEHOLDER


class ImageListModel(QAbstractListModel):
    def __init__(
        self, project: Project | None = None, task_id: int | None = None
    ) -> None:
        super().__init__()
        self._project = project
        self._task_id = task_id
        if project is not None and task_id is not None:
            self._images: list[Image] = project.repo.list_images_for_task(task_id)
        else:
            self._images = []
        self._cache: dict[int, QPixmap] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._images)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._images):
            return None
        img = self._images[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return img.filename
        if role == Qt.ItemDataRole.DecorationRole:
            return self._thumbnail(img)
        if role == Qt.ItemDataRole.UserRole:
            return img
        return None

    def _thumbnail(self, img: Image) -> QPixmap:
        if img.thumbnail_filename is None or self._project is None:
            return _placeholder()
        if img.id in self._cache:
            return self._cache[img.id]
        path = self._project.thumbnails_dir / img.thumbnail_filename
        pm = QPixmap(str(path))
        if pm.isNull():
            pm = _placeholder()
        self._cache[img.id] = pm
        return pm

    def image_at(self, row: int) -> Image | None:
        if 0 <= row < len(self._images):
            return self._images[row]
        return None

    def total(self) -> int:
        return len(self._images)

    def refresh_missing_thumbnails(self) -> None:
        if self._project is None or self._task_id is None:
            return
        unknown_indices = [
            i for i, img in enumerate(self._images) if img.thumbnail_filename is None
        ]
        if not unknown_indices:
            return
        fresh = {
            img.id: img
            for img in self._project.repo.list_images_for_task(self._task_id)
        }
        changed = []
        for i in unknown_indices:
            old = self._images[i]
            new = fresh.get(old.id)
            if new is not None and new.thumbnail_filename is not None:
                self._images[i] = new
                changed.append(i)
        for i in changed:
            idx = self.index(i, 0)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DecorationRole])


class ImageItemDelegate(QStyledItemDelegate):
    NUMBER_WIDTH = 44
    THUMB_SIZE = 80
    PADDING = 6

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QSize:
        return QSize(
            self.NUMBER_WIDTH + self.THUMB_SIZE + 80 + self.PADDING * 4,
            self.THUMB_SIZE + self.PADDING * 2,
        )

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            text_color = option.palette.highlightedText().color()
        else:
            text_color = option.palette.text().color()

        x = option.rect.left() + self.PADDING
        y = option.rect.top() + self.PADDING
        h = option.rect.height() - self.PADDING * 2

        painter.save()
        font = painter.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            QRect(x, y, self.NUMBER_WIDTH, h),
            int(Qt.AlignmentFlag.AlignCenter),
            str(index.row() + 1),
        )
        painter.restore()

        thumb_x = x + self.NUMBER_WIDTH
        pixmap = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.THUMB_SIZE,
                self.THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            ox = (self.THUMB_SIZE - scaled.width()) // 2
            oy = (self.THUMB_SIZE - scaled.height()) // 2
            painter.drawPixmap(thumb_x + ox, y + oy, scaled)

        text_x = thumb_x + self.THUMB_SIZE + self.PADDING
        text_rect = QRect(
            text_x, y, max(0, option.rect.right() - text_x - self.PADDING), h
        )
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        painter.setPen(text_color)
        elided = painter.fontMetrics().elidedText(
            text, Qt.TextElideMode.ElideMiddle, text_rect.width()
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            elided,
        )


class ImageListView(QListView):
    image_selected = Signal(Image, int)

    def __init__(self) -> None:
        super().__init__()
        self.setSpacing(0)
        self.setUniformItemSizes(True)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setItemDelegate(ImageItemDelegate(self))
        self.setModel(ImageListModel())

    def set_task(self, project: Project | None, task_id: int | None) -> None:
        old_sel = self.selectionModel()
        if old_sel is not None:
            try:
                old_sel.currentChanged.disconnect(self._on_current_changed)
            except (RuntimeError, TypeError):
                pass
        model = ImageListModel(project, task_id)
        self.setModel(model)
        sel = self.selectionModel()
        if sel is not None:
            sel.currentChanged.connect(self._on_current_changed)
        if model.total() > 0:
            self.setCurrentIndex(model.index(0, 0))

    def _on_current_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        if not current.isValid():
            return
        model = self.model()
        if isinstance(model, ImageListModel):
            img = model.image_at(current.row())
            if img is not None:
                self.image_selected.emit(img, current.row())

    def select_row(self, row: int) -> None:
        model = self.model()
        if model is None or row < 0 or row >= model.rowCount():
            return
        self.setCurrentIndex(model.index(row, 0))

    def select_relative(self, delta: int) -> None:
        model = self.model()
        if model is None or model.rowCount() == 0:
            return
        current = self.currentIndex().row()
        if current < 0:
            current = 0
        new_row = max(0, min(model.rowCount() - 1, current + delta))
        if new_row != current:
            self.select_row(new_row)

    def refresh_thumbnails(self) -> None:
        model = self.model()
        if isinstance(model, ImageListModel):
            model.refresh_missing_thumbnails()
