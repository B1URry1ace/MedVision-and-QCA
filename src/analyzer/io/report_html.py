from __future__ import annotations
from pathlib import Path
from src.analyzer.core.data_models import VesselMetrics


def export_html(metrics: list[VesselMetrics], path: Path) -> None:
    rows = ""
    for m in metrics:
        s = m.stenosis_percent
        color = "#16a34a" if s < 25 else ("#f0883e" if s < 50 else "#f85149")
        rows += (
            f"<tr><td>{m.image_name}</td><td>{m.class_name}</td>"
            f"<td>{m.mask_area_px}</td><td>{m.skeleton_length_px:.1f}</td>"
            f"<td>{m.diameter_min_px:.2f}</td><td>{m.diameter_mean_px:.2f}</td>"
            f"<td>{m.diameter_ref_px:.2f}</td>"
            f"<td style='color:{color};font-weight:bold'>{s:.1f}%</td>"
            f"<td style='color:{color}'>{m.stenosis_grade()}</td>"
            f"<td>{m.tortuosity:.3f}</td></tr>\n"
        )
    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8"><title>Отчёт QCA</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#c9d1d9;margin:24px}}
h1{{color:#58a6ff}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th{{background:#1f6feb;color:#fff;padding:8px 12px;text-align:left}}
td{{padding:6px 12px;border-bottom:1px solid #21262d}}
tr:nth-child(even) td{{background:#161b22}}
tr:hover td{{background:#1f3a6e}}
</style></head><body>
<h1>Отчёт по анализу коронарных ангиограмм (QCA)</h1>
<p>Объектов: <b>{len(metrics)}</b></p>
<table><thead><tr>
<th>Файл</th><th>Класс</th><th>Площадь(px²)</th>
<th>L скелета(px)</th><th>D мин(px)</th><th>D ср(px)</th>
<th>D реф(px)</th><th>Стеноз</th><th>Степень</th><th>Извитость</th>
</tr></thead><tbody>{rows}</tbody></table>
</body></html>"""
    path.write_text(html, encoding="utf-8")