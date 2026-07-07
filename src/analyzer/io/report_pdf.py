from __future__ import annotations
from pathlib import Path
from src.analyzer.core.data_models import VesselMetrics


def export_pdf(metrics: list[VesselMetrics], path: Path) -> None:
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors as rl_colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
    except ImportError:
        raise ImportError("Установите reportlab: pip install reportlab")

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4),
                            rightMargin=15 * mm, leftMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title", fontSize=16, fontName="Helvetica-Bold",
        spaceAfter=8, textColor=rl_colors.HexColor("#1f6feb"),
    )
    story = [
        Paragraph("Отчёт по анализу коронарных ангиограмм", title_style),
        Spacer(1, 8 * mm),
    ]

    data = [["Файл", "Класс", "Стеноз %", "Степень",
             "D мин", "D ср", "D реф", "Извит."]]
    for m in metrics:
        data.append([
            m.image_name[:30], m.class_name[:20],
            f"{m.stenosis_percent:.1f}", m.stenosis_grade()[:18],
            f"{m.diameter_min_px:.2f}", f"{m.diameter_mean_px:.2f}",
            f"{m.diameter_ref_px:.2f}", f"{m.tortuosity:.3f}",
        ])

    col_w = [60*mm, 45*mm, 20*mm, 50*mm, 18*mm, 18*mm, 18*mm, 18*mm]
    t = Table(data, colWidths=col_w, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#1f6feb")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [rl_colors.HexColor("#f6f8fa"), rl_colors.HexColor("#ffffff")]),
        ("GRID", (0, 0), (-1, -1), 0.3, rl_colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(t)
    doc.build(story)