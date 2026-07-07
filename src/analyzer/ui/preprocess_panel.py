from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QVBoxLayout,
)


class PreprocessPanel(QGroupBox):
    """Панель настроек предобработки изображения."""

    changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Предобработка изображения", parent)
        self._build_ui()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)

        self.chk_window = QCheckBox(
            "Авто-windowing (отбросить 1%/99% гистограммы)"
        )
        lay.addWidget(self.chk_window)

        h = QHBoxLayout()
        self.chk_clahe = QCheckBox("CLAHE  clip:")
        self.spin_clahe_clip = QDoubleSpinBox()
        self.spin_clahe_clip.setRange(0.5, 10.0)
        self.spin_clahe_clip.setValue(2.0)
        self.spin_clahe_clip.setSingleStep(0.5)
        self.spin_clahe_clip.setFixedWidth(70)
        h.addWidget(self.chk_clahe)
        h.addWidget(self.spin_clahe_clip)
        h.addWidget(QLabel("tile:"))
        self.spin_clahe_tile = QSpinBox()
        self.spin_clahe_tile.setRange(4, 32)
        self.spin_clahe_tile.setValue(8)
        self.spin_clahe_tile.setFixedWidth(55)
        h.addWidget(self.spin_clahe_tile)
        h.addStretch()
        lay.addLayout(h)

        self.chk_frangi = QCheckBox(
            "Vesselness (Frangi) — только для просмотра"
        )
        lay.addWidget(self.chk_frangi)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        def _slider_row(label_text: str, lo: int, hi: int, val: int):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(90)
            sl = QSlider()
            sl.setOrientation(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Orientation.Horizontal)
            sl.setRange(lo, hi)
            sl.setValue(val)
            vl = QLabel(str(val))
            vl.setFixedWidth(35)
            sl.valueChanged.connect(lambda v, l=vl: l.setText(str(v)))
            sl.valueChanged.connect(self.changed)
            row.addWidget(lbl)
            row.addWidget(sl)
            row.addWidget(vl)
            return row, sl

        r, self.sl_bright   = _slider_row("Яркость:",  -100, 100, 0)
        lay.addLayout(r)
        r, self.sl_contrast = _slider_row("Контраст:", -100, 100, 0)
        lay.addLayout(r)

        h2 = QHBoxLayout()
        h2.addWidget(QLabel("Гамма:"))
        self.sl_gamma = QSlider()
        self.sl_gamma.setOrientation(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Orientation.Horizontal)
        self.sl_gamma.setRange(10, 300)
        self.sl_gamma.setValue(100)
        self.lbl_gamma = QLabel("1.00")
        self.lbl_gamma.setFixedWidth(35)
        self.sl_gamma.valueChanged.connect(
            lambda v: self.lbl_gamma.setText(f"{v / 100:.2f}")
        )
        self.sl_gamma.valueChanged.connect(self.changed)
        h2.addWidget(self.sl_gamma)
        h2.addWidget(self.lbl_gamma)
        lay.addLayout(h2)

        btn_reset = QPushButton("Сбросить")
        btn_reset.clicked.connect(self.reset)
        lay.addWidget(btn_reset)

        for w in [self.chk_window, self.chk_clahe, self.chk_frangi,
                  self.spin_clahe_clip, self.spin_clahe_tile, self.sl_bright,
                  self.sl_contrast]:
            sig = getattr(w, "stateChanged", None) or getattr(w, "valueChanged", None)
            if sig:
                sig.connect(self.changed)

    def reset(self) -> None:
        for w in [self.chk_window, self.chk_clahe, self.chk_frangi]:
            w.setChecked(False)
        self.sl_bright.setValue(0)
        self.sl_contrast.setValue(0)
        self.sl_gamma.setValue(100)

    def get_params(self) -> dict:
        return {
            "auto_window": self.chk_window.isChecked(),
            "clahe":       self.chk_clahe.isChecked(),
            "clahe_clip":  self.spin_clahe_clip.value(),
            "clahe_tile":  self.spin_clahe_tile.value(),
            "frangi":      self.chk_frangi.isChecked(),
            "brightness":  self.sl_bright.value(),
            "contrast":    self.sl_contrast.value(),
            "gamma":       self.sl_gamma.value() / 100.0,
        }