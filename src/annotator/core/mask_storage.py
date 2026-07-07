from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image as PILImage


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def instance_mask_filename(image_id: int, instance_id: int) -> str:
    return f"{image_id:08d}_inst_{instance_id:06d}.png"


def discover_instance_masks(masks_dir: Path, image_id: int) -> dict[int, str]:
    prefix = f"{image_id:08d}_inst_"
    result: dict[int, str] = {}
    if not masks_dir.exists():
        return result
    for p in masks_dir.glob(f"{prefix}*.png"):
        stem = p.stem
        try:
            idx = stem.index("_inst_")
        except ValueError:
            continue
        try:
            instance_id = int(stem[idx + len("_inst_"):])
        except ValueError:
            continue
        result[instance_id] = p.name
    return result


def load_binary_mask(path: Path, shape: tuple[int, int]) -> np.ndarray:
    if not path.exists():
        return np.zeros(shape, dtype=np.uint8)
    try:
        with PILImage.open(path) as im:
            arr = np.array(im.convert("L"), dtype=np.uint8)
        if arr.shape != shape:
            return np.zeros(shape, dtype=np.uint8)
        return (arr > 0).astype(np.uint8)
    except Exception:
        return np.zeros(shape, dtype=np.uint8)


def save_binary_mask(path: Path, mask: np.ndarray) -> None:
    visible = (mask > 0).astype(np.uint8) * 255
    pim = PILImage.fromarray(visible, mode="L")
    pim.save(path, "PNG", optimize=True)


def delete_mask_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
