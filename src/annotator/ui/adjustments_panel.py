#adjustments_panel.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class AdjustmentsPanel(QWidget):
    adjustments_changed = Signal(int, int, float)
    clahe_changed = Signal(bool, float, int)
    frangi_changed = Signal(bool)
    diameter_map_changed = Signal(bool)
    opacity_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self._brightness = 0
        self._contrast = 0
        self._gamma = 1.0
        self._clahe_enabled = False
        self._clahe_clip = 2.0
        self._clahe_tile = 8
        self._frangi_enabled = False
        self._diameter_map_enabled = False
        self._opacity = 0.55
        self._updating = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        title = QLabel("Отображение")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title)

        self.brightness_label = QLabel("Яркость: 0")
        layout.addWidget(self.brightness_label)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self._on_brightness)
        layout.addWidget(self.brightness_slider)

        self.contrast_label = QLabel("Контраст: 0")
        layout.addWidget(self.contrast_label)
        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(-100, 100)
        self.contrast_slider.setValue(0)
        self.contrast_slider.valueChanged.connect(self._on_contrast)
        layout.addWidget(self.contrast_slider)

        self.gamma_label = QLabel("Гамма: 1.00")
        layout.addWidget(self.gamma_label)
        self.gamma_slider = QSlider(Qt.Orientation.Horizontal)
        self.gamma_slider.setRange(50, 250)
        self.gamma_slider.setValue(100)
        self.gamma_slider.valueChanged.connect(self._on_gamma)
        layout.addWidget(self.gamma_slider)

        reset_btn = QPushButton("Сбросить яркость/контраст/гамму")
        reset_btn.clicked.connect(self.reset_lut)
        layout.addWidget(reset_btn)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep1)

        adaptive_title = QLabel("Адаптивно")
        adaptive_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(adaptive_title)

        self.clahe_cb = QCheckBox("CLAHE (адаптивная гистограммная коррекция)")
        self.clahe_cb.setChecked(self._clahe_enabled)
        self.clahe_cb.toggled.connect(self._on_clahe_toggled)
        layout.addWidget(self.clahe_cb)

        params = QFormLayout()
        params.setContentsMargins(0, 0, 0, 0)
        self.clahe_clip_spin = QDoubleSpinBox()
        self.clahe_clip_spin.setRange(0.5, 10.0)
        self.clahe_clip_spin.setSingleStep(0.5)
        self.clahe_clip_spin.setValue(self._clahe_clip)
        self.clahe_clip_spin.setDecimals(2)
        self.clahe_clip_spin.valueChanged.connect(self._on_clahe_clip_changed)
        params.addRow("Clip limit:", self.clahe_clip_spin)

        self.clahe_tile_spin = QSpinBox()
        self.clahe_tile_spin.setRange(2, 32)
        self.clahe_tile_spin.setValue(self._clahe_tile)
        self.clahe_tile_spin.valueChanged.connect(self._on_clahe_tile_changed)
        params.addRow("Размер сетки:", self.clahe_tile_spin)
        layout.addLayout(params)

        self.frangi_cb = QCheckBox(
            "Frangi (выделение трубчатых структур)"
        )
        self.frangi_cb.setToolTip(
            "Подсветка сосудов на изображении. "
            "Применяется до CLAHE. Первый расчёт занимает ~3 с."
        )
        self.frangi_cb.setChecked(self._frangi_enabled)
        self.frangi_cb.toggled.connect(self._on_frangi_toggled)
        layout.addWidget(self.frangi_cb)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        masks_title = QLabel("Маски")
        masks_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(masks_title)

        self.opacity_label = QLabel("Прозрачность: 55%")
        layout.addWidget(self.opacity_label)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(int(self._opacity * 100))
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        layout.addWidget(self.opacity_slider)

        self.diameter_cb = QCheckBox(
            "Карта диаметров (вместо цветов классов)"
        )
        self.diameter_cb.setToolTip(
            "Цвет наложения по локальной толщине сосуда: "
            "синий — тонкое, красный — толстое (Jet colormap)."
        )
        self.diameter_cb.setChecked(self._diameter_map_enabled)
        self.diameter_cb.toggled.connect(self._on_diameter_toggled)
        layout.addWidget(self.diameter_cb)

        layout.addStretch()

    def _format_brightness(self, v: int) -> str:
        return f"Яркость: {v:+d}" if v != 0 else "Яркость: 0"

    def _format_contrast(self, v: int) -> str:
        return f"Контраст: {v:+d}" if v != 0 else "Контраст: 0"

    def _format_gamma(self, v: float) -> str:
        return f"Гамма: {v:.2f}"

    def _emit_lut(self) -> None:
        self.adjustments_changed.emit(
            self._brightness, self._contrast, self._gamma
        )

    def _emit_clahe(self) -> None:
        self.clahe_changed.emit(
            self._clahe_enabled, self._clahe_clip, self._clahe_tile
        )

    def _on_brightness(self, value: int) -> None:
        self._brightness = value
        self.brightness_label.setText(self._format_brightness(value))
        if not self._updating:
            self._emit_lut()

    def _on_contrast(self, value: int) -> None:
        self._contrast = value
        self.contrast_label.setText(self._format_contrast(value))
        if not self._updating:
            self._emit_lut()

    def _on_gamma(self, value: int) -> None:
        self._gamma = value / 100.0
        self.gamma_label.setText(self._format_gamma(self._gamma))
        if not self._updating:
            self._emit_lut()

    def _on_clahe_toggled(self, checked: bool) -> None:
        self._clahe_enabled = checked
        if not self._updating:
            self._emit_clahe()

    def _on_clahe_clip_changed(self, value: float) -> None:
        self._clahe_clip = float(value)
        if not self._updating:
            self._emit_clahe()

    def _on_clahe_tile_changed(self, value: int) -> None:
        self._clahe_tile = int(value)
        if not self._updating:
            self._emit_clahe()

    def _on_frangi_toggled(self, checked: bool) -> None:
        self._frangi_enabled = checked
        if not self._updating:
            self.frangi_changed.emit(checked)

    def _on_diameter_toggled(self, checked: bool) -> None:
        self._diameter_map_enabled = checked
        if not self._updating:
            self.diameter_map_changed.emit(checked)

    def _on_opacity_changed(self, value: int) -> None:
        self._opacity = value / 100.0
        self.opacity_label.setText(f"Прозрачность: {value}%")
        if not self._updating:
            self.opacity_changed.emit(self._opacity)

    def reset_lut(self) -> None:
        self.set_lut(0, 0, 1.0)

    def set_lut(self, brightness: int, contrast: int, gamma: float) -> None:
        self._updating = True
        try:
            self.brightness_slider.setValue(brightness)
            self.contrast_slider.setValue(contrast)
            self.gamma_slider.setValue(int(round(gamma * 100)))
        finally:
            self._updating = False
        self._emit_lut()

    def set_clahe(self, enabled: bool, clip: float, tile: int) -> None:
        self._updating = True
        try:
            self.clahe_cb.setChecked(enabled)
            self.clahe_clip_spin.setValue(clip)
            self.clahe_tile_spin.setValue(tile)
        finally:
            self._updating = False
        self._emit_clahe()

    def set_frangi(self, enabled: bool) -> None:
        self._updating = True
        try:
            self.frangi_cb.setChecked(enabled)
        finally:
            self._updating = False
        self.frangi_changed.emit(enabled)

    def set_diameter_map(self, enabled: bool) -> None:
        self._updating = True
        try:
            self.diameter_cb.setChecked(enabled)
        finally:
            self._updating = False
        self.diameter_map_changed.emit(enabled)

    def set_opacity(self, value: float) -> None:
        self._updating = True
        try:
            self.opacity_slider.setValue(int(round(value * 100)))
        finally:
            self._updating = False
        self._opacity = value
        self.opacity_changed.emit(value)

    def set_values(self, brightness: int, contrast: int, gamma: float) -> None:
        self.set_lut(brightness, contrast, gamma)
