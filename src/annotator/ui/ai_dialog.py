#ai_dialog.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from src.annotator.core.models import Label as LabelModel


def _swatch(color: str, size: int = 16) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(color))
    return QIcon(pm)


class AiDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        model_files: list[Path],
        labels: list[LabelModel],
        cuda_available: bool,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI разметка")
        self.setModal(True)
        self._model_files = list(model_files)

        layout = QFormLayout(self)

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(260)
        for p in self._model_files:
            self.model_combo.addItem(p.name, str(p))
        layout.addRow("Модель:", self.model_combo)

        self.class_combo = QComboBox()
        self.class_combo.setMinimumWidth(220)
        for label in labels:
            if label.id == 0:
                continue
            self.class_combo.addItem(
                _swatch(label.color), label.name, label.id
            )
        layout.addRow("Класс:", self.class_combo)

        self.conf_spin = QDoubleSpinBox()
        self.conf_spin.setRange(0.05, 0.95)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setValue(0.25)
        self.conf_spin.setDecimals(2)
        layout.addRow("Порог уверенности:", self.conf_spin)

        self.use_gpu_cb = QCheckBox(
            "Использовать GPU (CUDA)"
            if cuda_available
            else "GPU недоступен — расчёт на CPU"
        )
        self.use_gpu_cb.setChecked(cuda_available)
        self.use_gpu_cb.setEnabled(cuda_available)
        layout.addRow(self.use_gpu_cb)

        self.batch_cb = QCheckBox(
            "Применить ко всем неразмеченным изображениям задачи"
        )
        self.batch_cb.setChecked(False)
        layout.addRow(self.batch_cb)

        info = QLabel(
            "Все обнаруженные объекты будут созданы как новые инстансы "
            "выбранного класса. Последний создаётся выделенным."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #555;")
        layout.addRow(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Запустить")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def selected_model_path(self) -> Path | None:
        data = self.model_combo.currentData()
        return Path(data) if data else None

    def selected_label_id(self) -> int | None:
        return self.class_combo.currentData()

    def confidence(self) -> float:
        return float(self.conf_spin.value())

    def use_gpu(self) -> bool:
        return self.use_gpu_cb.isChecked()

    def batch_mode(self) -> bool:
        return self.batch_cb.isChecked()


class AiProgressDialog(QDialog):
    def __init__(
        self, parent: QWidget | None, model_name: str, on_gpu: bool
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI разметка")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setWindowFlag(
            Qt.WindowType.WindowContextHelpButtonHint, False
        )
        self.setFixedSize(380, 110)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        device_text = "GPU (CUDA)" if on_gpu else "CPU"
        self.message_label = QLabel(
            f"Запуск {model_name} на {device_text}…"
        )
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)
        bar = QProgressBar()
        bar.setRange(0, 0)
        bar.setTextVisible(False)
        layout.addWidget(bar)

    def set_message(self, text: str) -> None:
        self.message_label.setText(text)
