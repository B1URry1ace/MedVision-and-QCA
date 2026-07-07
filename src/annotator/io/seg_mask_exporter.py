from __future__ import annotations

import colorsys
import shutil
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image as PILImage

from src.annotator.core.mask_storage import (
    discover_instance_masks, hex_to_rgb, load_binary_mask)
from src.annotator.core.project import Project


class ExportCancelled(Exception):
    pass


ProgressCallback = Callable[[int, int], None]


def _build_class_palette(label_colors: dict[int, str]) -> bytes:
    palette = bytearray(768)
    for label_id, hex_color in label_colors.items():
        if 0 <= label_id < 256:
            r, g, b = hex_to_rgb(hex_color)
            palette[label_id * 3] = r
            palette[label_id * 3 + 1] = g
            palette[label_id * 3 + 2] = b
    return bytes(palette)


def _build_object_palette() -> bytes:
    palette = bytearray(768)
    for i in range(1, 256):
        hue = ((i - 1) * 137.508) % 360
        r, g, b = colorsys.hsv_to_rgb(hue / 360.0, 0.65, 0.85)
        palette[i * 3] = int(r * 255)
        palette[i * 3 + 1] = int(g * 255)
        palette[i * 3 + 2] = int(b * 255)
    return bytes(palette)


def _write_labelmap(path: Path, labels: list) -> None:
    ordered = sorted(labels, key=lambda l: l.id)
    with path.open("w", encoding="utf-8") as f:
        f.write("# label:color_rgb:parts:actions\n")
        for label in ordered:
            r, g, b = hex_to_rgb(label.color)
            f.write(f"{label.name}:{r},{g},{b}::\n")


def export_task(project: Project, task_id: int, target_dir: Path, *,
                only_annotated: bool = True, copy_originals: bool = True,
                include_segmentation_object: bool = True,
                progress_callback: ProgressCallback | None = None) -> int:
    target_dir.mkdir(parents=True, exist_ok=True)
    seg_class_dir = target_dir / "SegmentationClass"
    seg_class_dir.mkdir(exist_ok=True)
    seg_obj_dir = target_dir / "SegmentationObject"
    if include_segmentation_object:
        seg_obj_dir.mkdir(exist_ok=True)
    images_dir = target_dir / "JPEGImages"
    if copy_originals:
        images_dir.mkdir(exist_ok=True)
    sets_dir = target_dir / "ImageSets" / "Segmentation"
    sets_dir.mkdir(parents=True, exist_ok=True)

    labels = project.repo.list_labels()
    _write_labelmap(target_dir / "labelmap.txt", labels)
    label_colors = {label.id: label.color for label in labels}
    class_palette = _build_class_palette(label_colors)
    object_palette = _build_object_palette() if include_segmentation_object else None

    all_images = project.repo.list_images_for_task(task_id)
    images = ([img for img in all_images if img.is_annotated]
              if only_annotated else all_images)
    total = len(images)
    written_stems: list[str] = []

    for i, img in enumerate(images):
        if img.width and img.height:
            shape: tuple[int, int] = (img.height, img.width)
        else:
            try:
                with PILImage.open(img.source_path) as im:
                    shape = (im.height, im.width)
            except Exception:
                if progress_callback:
                    progress_callback(i + 1, total)
                continue

        sem_mask = np.zeros(shape, dtype=np.uint8)
        obj_mask = np.zeros(shape, dtype=np.uint8) if include_segmentation_object else None

        records = project.repo.list_instances_for_image(img.id)
        discovered = discover_instance_masks(project.masks_dir, img.id)
        local_index = 0
        for rec in sorted(records, key=lambda r: r.instance_id):
            if rec.label_id is None or rec.instance_id not in discovered:
                continue
            mask_path = project.masks_dir / discovered[rec.instance_id]
            inst_mask = load_binary_mask(mask_path, shape)
            sem_mask[inst_mask > 0] = rec.label_id
            if obj_mask is not None:
                local_index += 1
                if local_index < 256:
                    obj_mask[inst_mask > 0] = local_index

        stem = Path(img.filename).stem
        sem_pim = PILImage.fromarray(sem_mask, mode="P")
        sem_pim.putpalette(class_palette)
        sem_pim.save(seg_class_dir / f"{stem}.png", "PNG", optimize=True)

        if obj_mask is not None and object_palette is not None:
            obj_pim = PILImage.fromarray(obj_mask, mode="P")
            obj_pim.putpalette(object_palette)
            obj_pim.save(seg_obj_dir / f"{stem}.png", "PNG", optimize=True)

        if copy_originals:
            src_path = Path(img.source_path)
            if src_path.exists():
                try:
                    shutil.copy2(src_path, images_dir / img.filename)
                except OSError:
                    pass

        written_stems.append(stem)
        if progress_callback:
            progress_callback(i + 1, total)

    with (sets_dir / "default.txt").open("w", encoding="utf-8") as f:
        for stem in written_stems:
            f.write(f"{stem}\n")

    return len(written_stems)
