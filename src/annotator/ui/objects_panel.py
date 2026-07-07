#objects_panel.py
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.annotator.core.models import Label as LabelModel


def _swatch(color: str, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return QIcon(pm)


@dataclass
class ObjectEntry:
    instance_id: int
    label_id: int | None
    label_name: str
    label_color: str
    per_class_index: int


class ChangeClassDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        labels: list[LabelModel],
        current_label_id: int | None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Сменить класс объекта")
        self.setModal(True)
        layout = QFormLayout(self)
        self.combo = QComboBox()
        self.combo.setMinimumWidth(220)
        for label in labels:
            if label.id == 0:
                continue
            self.combo.addItem(_swatch(label.color), label.name, label.id)
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == current_label_id:
                self.combo.setCurrentIndex(i)
                break
        layout.addRow("Новый класс:", self.combo)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_label_id(self) -> int | None:
        return self.combo.currentData()


class ObjectsPanel(QWidget):
    visibility_changed = Signal(int, bool)
    delete_requested = Signal(int)
    change_class_requested = Signal(int, int)
    selection_changed = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[ObjectEntry] = []
        self._available_labels: list[LabelModel] = []
        self._visibility: dict[int, bool] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Объекты на изображении")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemChanged.connect(self._on_item_check_changed)
        layout.addWidget(self.list_widget, stretch=1)

        self.empty_label = QLabel(
            "Объектов на этом изображении пока нет.\n"
            "Используй инструмент «Полигон» или «Кисть»."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; padding: 20px;")
        layout.addWidget(self.empty_label, stretch=1)

        btn_row = QHBoxLayout()
        self.change_btn = QPushButton("Сменить класс")
        self.change_btn.clicked.connect(self._on_change_class)
        self.change_btn.setEnabled(False)
        btn_row.addWidget(self.change_btn)
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

    def set_data(
        self,
        entries: list[ObjectEntry],
        visibility: dict[int, bool],
        available_labels: list[LabelModel],
    ) -> None:
        prev_selected = self.selected_instance_id()
        self._entries = list(entries)
        self._visibility = dict(visibility)
        self._available_labels = list(available_labels)
        self._rebuild_list(prev_selected)

    def _rebuild_list(self, restore_id: int | None = None) -> None:
        self.list_widget.blockSignals(True)
        restore_row = -1
        try:
            self.list_widget.clear()
            for i, entry in enumerate(self._entries):
                text = (
                    f"{entry.label_name} #{entry.per_class_index}"
                    if entry.label_id is not None
                    else f"(класс удалён) #{entry.instance_id}"
                )
                color = entry.label_color or "#888888"
                item = QListWidgetItem(_swatch(color), text)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                visible = self._visibility.get(entry.instance_id, True)
                item.setCheckState(
                    Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
                )
                item.setData(Qt.ItemDataRole.UserRole, entry.instance_id)
                self.list_widget.addItem(item)
                if entry.instance_id == restore_id:
                    restore_row = i
            has = bool(self._entries)
            self.list_widget.setVisible(has)
            self.empty_label.setVisible(not has)
            if restore_row >= 0:
                self.list_widget.setCurrentRow(restore_row)
        finally:
            self.list_widget.blockSignals(False)
        self._on_selection_changed()

    def _selected_entry(self) -> ObjectEntry | None:
        items = self.list_widget.selectedItems()
        if not items:
            return None
        iid = items[0].data(Qt.ItemDataRole.UserRole)
        for e in self._entries:
            if e.instance_id == iid:
                return e
        return None

    def selected_instance_id(self) -> int | None:
        items = self.list_widget.selectedItems()
        if not items:
            return None
        iid = items[0].data(Qt.ItemDataRole.UserRole)
        return int(iid) if iid is not None else None

    def set_selected_instance_id(self, instance_id: int | None) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == instance_id:
                self.list_widget.setCurrentRow(row)
                return
        self.list_widget.clearSelection()

    def _update_buttons(self) -> None:
        entry = self._selected_entry()
        self.change_btn.setEnabled(
            entry is not None and bool(self._available_labels)
        )
        self.delete_btn.setEnabled(entry is not None)

    def _on_selection_changed(self) -> None:
        self._update_buttons()
        iid = self.selected_instance_id()
        self.selection_changed.emit(iid if iid is not None else -1)

    def _on_item_check_changed(self, item: QListWidgetItem) -> None:
        iid = item.data(Qt.ItemDataRole.UserRole)
        if iid is None:
            return
        visible = item.checkState() == Qt.CheckState.Checked
        self._visibility[iid] = visible
        self.visibility_changed.emit(int(iid), visible)

    def _on_change_class(self) -> None:
        entry = self._selected_entry()
        if entry is None or not self._available_labels:
            return
        dialog = ChangeClassDialog(
            self, self._available_labels, entry.label_id
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_label_id = dialog.selected_label_id()
        if new_label_id is None or new_label_id == entry.label_id:
            return
        self.change_class_requested.emit(entry.instance_id, int(new_label_id))

    def _on_delete(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        resp = QMessageBox.question(
            self,
            "Удалить объект?",
            f"Удалить объект «{entry.label_name} #{entry.per_class_index}»?\n"
            "Файл маски этого объекта будет стёрт с диска.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        self.delete_requested.emit(entry.instance_id)
