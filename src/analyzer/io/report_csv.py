from __future__ import annotations
import csv
from pathlib import Path
from src.analyzer.core.data_models import VesselMetrics


def export_csv(metrics: list[VesselMetrics], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "image_name", "class_id", "class_name", "laplacian_var",
            "mask_area_px", "skeleton_length_px", "vessel_length_mm",
            "diameter_min_px", "diameter_max_px", "diameter_mean_px",
            "diameter_ref_px", "stenosis_percent", "stenosis_grade",
            "tortuosity", "proximal_diameter_px", "distal_diameter_px",
        ])
        for m in metrics:
            writer.writerow([
                m.image_name, m.class_id, m.class_name,
                f"{m.laplacian_var:.2f}", m.mask_area_px,
                f"{m.skeleton_length_px:.2f}", f"{m.vessel_length_mm:.4f}",
                f"{m.diameter_min_px:.4f}", f"{m.diameter_max_px:.4f}",
                f"{m.diameter_mean_px:.4f}", f"{m.diameter_ref_px:.4f}",
                f"{m.stenosis_percent:.2f}", m.stenosis_grade(),
                f"{m.tortuosity:.4f}", f"{m.proximal_diameter_px:.4f}",
                f"{m.distal_diameter_px:.4f}",
            ])