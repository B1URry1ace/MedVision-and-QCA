from __future__ import annotations
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHeaderView, QLabel, QMessageBox,
    QPushButton, QScrollArea, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
from src.analyzer.core.data_models import ImageResult, VesselMetrics
from src.analyzer.io.report_csv import export_csv
from src.analyzer.io.report_html import export_html
from src.analyzer.io.report_pdf import export_pdf


class ReportDialog(QDialog):
    def __init__(self, results: list[ImageResult], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Сводный отчёт")
        self.setMinimumSize(900, 650)
        self.results = results
        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)

        btn_bar = QHBoxLayout()
        self.btn_csv  = QPushButton("Экспорт CSV")
        self.btn_pdf  = QPushButton("Экспорт PDF")
        self.btn_html = QPushButton("Экспорт HTML")
        for btn in (self.btn_csv, self.btn_pdf, self.btn_html):
            btn_bar.addWidget(btn)
        btn_bar.addStretch()
        lay.addLayout(btn_bar)

        tabs = QTabWidget()
        lay.addWidget(tabs)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        tabs.addTab(self.summary_text, "Сводка")

        self.table = QTableWidget()
        tabs.addTab(self.table, "Все метрики")

        self.chart_label = QLabel()
        self.chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidget(self.chart_label)
        scroll.setWidgetResizable(True)
        tabs.addTab(scroll, "Графики")

        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_pdf.clicked.connect(self._export_pdf)
        self.btn_html.clicked.connect(self._export_html)

    def _all_metrics(self) -> list[VesselMetrics]:
        out = []
        for r in self.results:
            out.extend(r.metrics)
        return out

    def _populate(self) -> None:
        all_m = self._all_metrics()
        total   = len(self.results)
        loaded  = sum(1 for r in self.results if r.loaded)
        skipped = sum(1 for r in self.results if r.skipped_quality)
        errors  = sum(1 for r in self.results if r.error)
        cnt     = {}
        for m in all_m:
            cnt[m.class_id] = cnt.get(m.class_id, 0) + 1
        stenoses = [m.stenosis_percent for m in all_m]
        diams    = [m.diameter_mean_px for m in all_m if m.diameter_mean_px > 0]

        if all_m:
            summary = (
                f"Изображений загружено:     {total}\n"
                f"Успешно обработано:        {loaded}\n"
                f"Пропущено (низкое кач.):   {skipped}\n"
                f"Ошибки:                    {errors}\n\n"
                f"Right coronary artery:     {cnt.get(0, 0)} объектов\n"
                f"Left coronary artery:      {cnt.get(1, 0)} объектов\n"
                f"Всего:                     {len(all_m)} объектов\n\n"
                f"Среднее:   {np.mean(stenoses):.1f}%  |  Медиана: {np.median(stenoses):.1f}%\n"
                f"Мин:       {np.min(stenoses):.1f}%   |  Макс:    {np.max(stenoses):.1f}%\n\n"
                f"Норма (<25%):       {sum(1 for s in stenoses if s < 25)}\n"
                f"Умеренный (25–70%): {sum(1 for s in stenoses if 25 <= s < 70)}\n"
                f"Тяжёлый (≥70%):     {sum(1 for s in stenoses if s >= 70)}\n\n"
                f"Средний диаметр (px): {np.mean(diams):.2f}" if diams else ""
            )
        else:
            summary = "Нет данных для отчёта."
        self.summary_text.setText(summary)

        cols = ["Файл", "Класс", "σ²Lap", "Площадь(px²)",
                "L скелета(px)", "Dmin(px)", "Dmax(px)",
                "Dmean(px)", "Dref(px)", "Стеноз(%)", "Степень",
                "Извитость", "Dprox(px)", "Ddist(px)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setRowCount(len(all_m))
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        for row, m in enumerate(all_m):
            for col, val in enumerate([
                m.image_name, m.class_name, f"{m.laplacian_var:.1f}",
                str(m.mask_area_px), f"{m.skeleton_length_px:.1f}",
                f"{m.diameter_min_px:.2f}", f"{m.diameter_max_px:.2f}",
                f"{m.diameter_mean_px:.2f}", f"{m.diameter_ref_px:.2f}",
                f"{m.stenosis_percent:.1f}", m.stenosis_grade(),
                f"{m.tortuosity:.3f}", f"{m.proximal_diameter_px:.2f}",
                f"{m.distal_diameter_px:.2f}",
            ]):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

        if all_m:
            self._build_charts(all_m)

    def _build_charts(self, all_m: list[VesselMetrics]) -> None:
        s_rca = [m.stenosis_percent for m in all_m if m.class_id == 0]
        s_lca = [m.stenosis_percent for m in all_m if m.class_id == 1]
        diams = [m.diameter_mean_px for m in all_m if m.diameter_mean_px > 0]
        torts = [m.tortuosity       for m in all_m if m.tortuosity > 0]

        fig, axes = plt.subplots(2, 2, figsize=(14, 10), facecolor="#0d1117")
        fig.suptitle("Распределение метрик сосудов", color="#c9d1d9", fontsize=14)

        def _style(ax, title, xlabel, ylabel):
            ax.set_facecolor("#161b22")
            ax.set_title(title, color="#58a6ff", fontsize=11)
            ax.set_xlabel(xlabel, color="#8b949e")
            ax.set_ylabel(ylabel, color="#8b949e")
            ax.tick_params(colors="#8b949e")
            for spine in ax.spines.values():
                spine.set_edgecolor("#21262d")

        ax = axes[0, 0]
        if s_rca: ax.hist(s_rca, bins=15, alpha=0.7, color="#f85149", label="RCA", edgecolor="#21262d")
        if s_lca: ax.hist(s_lca, bins=15, alpha=0.7, color="#58a6ff", label="LCA", edgecolor="#21262d")
        ax.axvline(50, color="#f0883e", ls="--", lw=1.5)
        ax.axvline(70, color="#f85149", ls="--", lw=1.5)
        ax.legend(facecolor="#21262d", edgecolor="#30363d", labelcolor="#c9d1d9")
        _style(ax, "Распределение % стеноза", "Стеноз (%)", "Кол-во")

        ax = axes[0, 1]
        if diams: ax.hist(diams, bins=15, color="#3fb950", edgecolor="#21262d", alpha=0.85)
        _style(ax, "Распределение среднего диаметра", "Диаметр (px)", "Кол-во")

        ax = axes[1, 0]
        if torts: ax.hist(torts, bins=15, color="#d2a8ff", edgecolor="#21262d", alpha=0.85)
        _style(ax, "Распределение извитости", "Извитость (L/d)", "Кол-во")

        ax = axes[1, 1]
        all_s = [m.stenosis_percent for m in all_m]
        all_d = [m.diameter_mean_px for m in all_m]
        colors = ["#f85149" if m.class_id == 0 else "#58a6ff" for m in all_m]
        if all_s:
            ax.scatter(all_s, all_d, c=colors, alpha=0.7, s=40, edgecolors="none")
            patches = [mpatches.Patch(color="#f85149", label="RCA"),
                       mpatches.Patch(color="#58a6ff", label="LCA")]
            ax.legend(handles=patches, facecolor="#21262d", edgecolor="#30363d", labelcolor="#c9d1d9")
        _style(ax, "Стеноз vs Диаметр", "Стеноз (%)", "Диаметр (px)")

        plt.tight_layout()
        fig.canvas.draw()
        buf = np.frombuffer(fig.canvas.buffer_rgba(), dtype=np.uint8)
        buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (4,))
        img_rgb = cv2.cvtColor(buf, cv2.COLOR_RGBA2RGB)
        h, w, _ = img_rgb.shape
        qimg = QImage(img_rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self.chart_label.setPixmap(QPixmap.fromImage(qimg))
        self.chart_label.resize(w, h)
        plt.close(fig)

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить CSV", "angio_report.csv", "CSV (*.csv)")
        if not path: return
        try:
            from pathlib import Path
            export_csv(self._all_metrics(), Path(path))
            QMessageBox.information(self, "Готово", f"CSV сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить PDF", "angio_report.pdf", "PDF (*.pdf)")
        if not path: return
        try:
            from pathlib import Path
            export_pdf(self._all_metrics(), Path(path))
            QMessageBox.information(self, "Готово", f"PDF сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _export_html(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить HTML", "angio_report.html", "HTML (*.html)")
        if not path: return
        try:
            from pathlib import Path
            export_html(self._all_metrics(), Path(path))
            QMessageBox.information(self, "Готово", f"HTML сохранён:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))