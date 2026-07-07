#classes_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.annotator.core.models import Label as LabelModel
from src.annotator.core.project import Project


DEFAULT_PALETTE = [
    "#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
    "#1abc9c", "#e67e22", "#34495e", "#27ae60", "#c0392b",
]


def _swatch(color: str, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return QIcon(pm)


class ClassDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        name: str = "",
        color: str = "#e74c3c",
        title: str = "Класс",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._color = color
        self._build_ui(name)

    def _build_ui(self, name: str) -> None:
        layout = QFormLayout(self)
        self.name_edit = QLineEdit(name)
        self.name_edit.setMinimumWidth(220)
        layout.addRow("Название:", self.name_edit)
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(100, 28)
        self._update_color_button()
        self.color_btn.clicked.connect(self._pick_color)
        layout.addRow("Цвет:", self.color_btn)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _update_color_button(self) -> None:
        self.color_btn.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid #888;"
        )

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Выбор цвета")
        if color.isValid():
            self._color = color.name()
            self._update_color_button()

    def get_values(self) -> tuple[str, str]:
        return self.name_edit.text().strip(), self._color


class ClassesPanel(QWidget):
    active_label_changed = Signal(object)
    labels_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._project: Project | None = None
        self._labels: list[LabelModel] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Классы")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title)

        self.add_btn = QPushButton("+ Добавить класс")
        self.add_btn.clicked.connect(self._on_add)
        layout.addWidget(self.add_btn)

        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemDoubleClicked.connect(lambda _: self._on_edit())
        layout.addWidget(self.list_widget, stretch=1)

        self.empty_label = QLabel("Классов пока нет.\nДобавь свой первый класс.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: gray; padding: 20px;")
        layout.addWidget(self.empty_label, stretch=1)

        btn_row = QHBoxLayout()
        self.edit_btn = QPushButton("Изменить")
        self.edit_btn.clicked.connect(self._on_edit)
        self.edit_btn.setEnabled(False)
        btn_row.addWidget(self.edit_btn)
        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

    def set_project(self, project: Project | None) -> None:
        self._project = project
        self.refresh()
        self.add_btn.setEnabled(project is not None)

    def refresh(self) -> None:
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            self._labels = []
            if self._project is None:
                self.list_widget.setVisible(False)
                self.empty_label.setVisible(True)
                self._update_buttons()
                return
            self._labels = [
                lbl for lbl in self._project.repo.list_labels() if lbl.id != 0
            ]
            for label in self._labels:
                item = QListWidgetItem(_swatch(label.color), label.name)
                item.setData(Qt.ItemDataRole.UserRole, label.id)
                self.list_widget.addItem(item)
            has = bool(self._labels)
            self.list_widget.setVisible(has)
            self.empty_label.setVisible(not has)
            if has:
                self.list_widget.setCurrentRow(0)
            else:
                self.active_label_changed.emit(None)
            self._update_buttons()
        finally:
            self.list_widget.blockSignals(False)

    def _selected_label(self) -> LabelModel | None:
        items = self.list_widget.selectedItems()
        if not items:
            return None
        label_id = items[0].data(Qt.ItemDataRole.UserRole)
        for label in self._labels:
            if label.id == label_id:
                return label
        return None

    def _update_buttons(self) -> None:
        label = self._selected_label()
        self.edit_btn.setEnabled(label is not None)
        self.delete_btn.setEnabled(label is not None)

    def _on_selection_changed(self) -> None:
        self._update_buttons()
        self.active_label_changed.emit(self._selected_label())

    def set_active_label_id(self, label_id: int | None) -> None:
        self.list_widget.blockSignals(True)
        try:
            target_row = -1
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == label_id:
                    target_row = i
                    break
            if target_row >= 0:
                self.list_widget.setCurrentRow(target_row)
            else:
                self.list_widget.clearSelection()
        finally:
            self.list_widget.blockSignals(False)

    def _on_add(self) -> None:
        if self._project is None:
            return
        default_color = DEFAULT_PALETTE[
            len(self._labels) % len(DEFAULT_PALETTE)
        ]
        dialog = ClassDialog(self, color=default_color, title="Новый класс")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, color = dialog.get_values()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Имя не может быть пустым.")
            return
        if self._project.repo.label_name_exists(name):
            QMessageBox.warning(
                self, "Ошибка", f"Класс '{name}' уже существует."
            )
            return
        self._project.repo.create_label(name, color)
        self.refresh()
        self.labels_changed.emit()

    def _on_edit(self) -> None:
        if self._project is None:
            return
        label = self._selected_label()
        if label is None:
            return
        dialog = ClassDialog(
            self, name=label.name, color=label.color, title="Изменить класс"
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, color = dialog.get_values()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Имя не может быть пустым.")
            return
        if name != label.name and self._project.repo.label_name_exists(
            name, exclude_id=label.id
        ):
            QMessageBox.warning(
                self, "Ошибка", f"Класс '{name}' уже существует."
            )
            return
        self._project.repo.update_label(label.id, name, color)
        self.refresh()
        self.labels_changed.emit()

    def _on_delete(self) -> None:
        if self._project is None:
            return
        label = self._selected_label()
        if label is None:
            return
        resp = QMessageBox.question(
            self,
            "Удалить класс?",
            f"Удалить класс '{label.name}'?\n\n"
            "Файлы масок этого класса на диске останутся (можешь удалить вручную "
            "в папке masks/ проекта).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            self._project.repo.delete_label(label.id)
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return
        self.refresh()
        self.labels_changed.emit()
