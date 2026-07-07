from __future__ import annotations
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from src.analyzer.core.data_models import VesselMetrics


class MetricsPanel(QWidget):
    """Панель отображения QCA-метрик текущего сосуда."""

    _FIELDS = [
        ("quality",        "Качество кадра (σ²Lap):"),
        ("class",          "Класс:"),
        ("area",           "Площадь маски (px²):"),
        ("skel_len",       "Длина скелета (px):"),
        ("vessel_len",     "Длина сосуда (мм):"),
        ("diam_min",       "Мин. диаметр (px):"),
        ("diam_max",       "Макс. диаметр (px):"),
        ("diam_mean",      "Средн. диаметр (px):"),
        ("diam_ref",       "Реф. диаметр, проксим. (px):"),
        ("stenosis",       "% стеноза:"),
        ("stenosis_grade", "Степень стеноза:"),
        ("tortuosity",     "Извитость (L/d):"),
        ("prox_d",         "Диам. проксим. (px):"),
        ("dist_d",         "Диам. дистал. (px):"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self._labels: dict[str, QLabel] = {}
        for key, lbl_text in self._FIELDS:
            row = QHBoxLayout()
            name_lbl = QLabel(lbl_text)
            name_lbl.setFixedWidth(220)
            name_lbl.setStyleSheet("color: #8b949e;")
            val_lbl = QLabel("—")
            val_lbl.setProperty("metric_role", "normal")
            self._labels[key] = val_lbl
            row.addWidget(name_lbl)
            row.addWidget(val_lbl)
            row.addStretch()
            lay.addLayout(row)
        lay.addStretch()

    def clear_metrics(self) -> None:
        for lbl in self._labels.values():
            lbl.setText("—")
            self._set_color(lbl, warn=False)

    def show_metrics(self, m: VesselMetrics,
                     laplacian: float | None = None) -> None:
        def _set(key: str, val: str, warn: bool = False) -> None:
            lbl = self._labels.get(key)
            if lbl:
                lbl.setText(val)
                self._set_color(lbl, warn)

        if laplacian is not None:
            _set("quality", f"{laplacian:.1f}")
        _set("class",          m.class_name)
        _set("area",           f"{m.mask_area_px:,}")
        _set("skel_len",       f"{m.skeleton_length_px:.1f}")
        _set("vessel_len",     f"{m.vessel_length_mm:.2f}")
        _set("diam_min",       f"{m.diameter_min_px:.2f}")
        _set("diam_max",       f"{m.diameter_max_px:.2f}")
        _set("diam_mean",      f"{m.diameter_mean_px:.2f}")
        _set("diam_ref",       f"{m.diameter_ref_px:.2f}")
        s = m.stenosis_percent
        _set("stenosis",       f"{s:.1f}%",          warn=(s >= 50))
        _set("stenosis_grade", m.stenosis_grade(),   warn=(s >= 50))
        _set("tortuosity",     f"{m.tortuosity:.3f}")
        _set("prox_d",         f"{m.proximal_diameter_px:.2f}")
        _set("dist_d",         f"{m.distal_diameter_px:.2f}")

    @staticmethod
    def _set_color(lbl: QLabel, warn: bool) -> None:
        color = "#f85149" if warn else "#3fb950"
        lbl.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: bold;"
        )