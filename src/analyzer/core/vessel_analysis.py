from __future__ import annotations
import cv2
import numpy as np
from scipy.ndimage import uniform_filter1d, convolve as nd_convolve
from skimage.morphology import skeletonize

from src.analyzer.core.data_models import VesselMetrics
from src.shared.constants import ANALYZER_CLASS_NAMES, ANALYZER_CLASS_COLORS


def _order_skeleton_points(skel_bool: np.ndarray) -> np.ndarray:
    """
    Упорядочить пиксели скелета от одного конца до другого.
    Возвращает (N, 2) массив координат [y, x].
    """
    coords = np.argwhere(skel_bool)
    if len(coords) == 0:
        return coords

    # Считаем число соседей (степень каждого пикселя)
    k = np.ones((3, 3), dtype=np.uint8)
    nb = nd_convolve(skel_bool.astype(np.uint8), k,
                     mode='constant') - skel_bool.astype(np.uint8)

    # Стартуем с конечной точки (степень 1)
    ep_mask = skel_bool & (nb == 1)
    endpoints = np.argwhere(ep_mask)
    start_idx = 0
    if len(endpoints):
        for ep in endpoints:
            d = np.sum((coords - ep) ** 2, axis=1)
            ci = int(np.argmin(d))
            if d[ci] < 2:
                start_idx = ci
                break

    used = np.zeros(len(coords), dtype=bool)
    ordered = [start_idx]
    used[start_idx] = True

    for _ in range(len(coords) - 1):
        cur = coords[ordered[-1]]
        dists = np.sum((coords - cur) ** 2, axis=1).astype(np.float64)
        dists[used] = np.inf
        nxt = int(np.argmin(dists))
        if not np.isfinite(dists[nxt]):
            break
        ordered.append(nxt)
        used[nxt] = True

    return coords[np.array(ordered)]


def compute_vessel_metrics(mask_binary: np.ndarray,
                           class_id: int,
                           image_name: str,
                           image_path: str,
                           scale_mm_per_px: float = 1.0) -> VesselMetrics:
    """
    Полный QCA-анализ одной бинарной маски сосуда.

    Алгоритм стеноза:
      1. Скелетонизация → упорядочение точек от конца к концу
      2. Сглаживание профиля диаметров (убирает пиксельный шум)
      3. Обрезка ±3% краёв (артефакты dist у границ маски)
      4. Минимум на сглаженном профиле = место стеноза
      5. Локальный D_ref = среднее 20% сосуда до и после минимума
         → убирает физиологический тейпер из расчёта
    """
    m = VesselMetrics()
    m.image_path = image_path
    m.image_name = image_name
    m.class_id = class_id
    m.class_name = ANALYZER_CLASS_NAMES.get(class_id, f"class_{class_id}")

    mask = (mask_binary > 0).astype(np.uint8)
    m.mask_area_px = int(mask.sum())
    if m.mask_area_px < 10:
        return m

    # ── Скелетонизация ────────────────────────────────────────────────────
    skel = skeletonize(mask.astype(bool))
    m.skeleton_length_px = float(skel.sum())
    m.vessel_length_mm = m.skeleton_length_px * scale_mm_per_px
    if skel.sum() < 5:
        return m

    # ── Distance Transform → профиль диаметров ───────────────────────────
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    ordered = _order_skeleton_points(skel)
    N = len(ordered)
    diameters = dist[ordered[:, 0], ordered[:, 1]] * 2.0

    m.diameter_min_px  = float(np.min(diameters))
    m.diameter_max_px  = float(np.max(diameters))
    m.diameter_mean_px = float(np.mean(diameters))

    # ── Сглаживание профиля ───────────────────────────────────────────────
    smooth_w = max(3, N // 15)
    smooth_d = uniform_filter1d(diameters.astype(float), size=smooth_w)

    # Убираем артефакты краёв (±3%)
    clip = max(2, int(N * 0.03))
    if N > clip * 3:
        inner_d   = smooth_d[clip:-clip]
        inner_raw = diameters[clip:-clip]
    else:
        inner_d   = smooth_d
        inner_raw = diameters

    # ── Минимум = место стеноза ───────────────────────────────────────────
    min_idx      = int(np.argmin(inner_d))
    d_min_smooth = float(inner_d[min_idx])
    m.diameter_stenosis_px = d_min_smooth

    # ── Локальные референсные сегменты ───────────────────────────────────
    L     = len(inner_d)
    ref_n = max(3, int(L * 0.20))
    gap   = max(2, int(L * 0.04))

    prox_seg = inner_d[max(0, min_idx - gap - ref_n) : max(0, min_idx - gap)]
    dist_seg = inner_d[min(L, min_idx + gap) : min(L, min_idx + gap + ref_n)]

    m.proximal_diameter_px = float(np.mean(prox_seg)) if len(prox_seg) else float(np.mean(inner_raw))
    m.distal_diameter_px   = float(np.mean(dist_seg)) if len(dist_seg) else float(np.mean(inner_raw))

    # Интерполируем D_ref по положению стеноза вдоль сосуда
    if len(prox_seg) >= 2 and len(dist_seg) >= 2:
        t     = min_idx / max(L - 1, 1)
        d_ref = m.proximal_diameter_px * (1 - t) + m.distal_diameter_px * t
    elif len(prox_seg) >= 2:
        d_ref = m.proximal_diameter_px
    elif len(dist_seg) >= 2:
        d_ref = m.distal_diameter_px
    else:
        d_ref = float(np.percentile(inner_d, 75))

    m.diameter_ref_px = float(d_ref)

    # ── % стеноза ─────────────────────────────────────────────────────────
    if d_ref > 0:
        m.stenosis_percent = float(np.clip(
            (d_ref - d_min_smooth) / d_ref * 100.0, 0.0, 100.0
        ))

    # ── Извитость ─────────────────────────────────────────────────────────
    if N >= 2:
        dy = float(ordered[-1, 0] - ordered[0, 0])
        dx = float(ordered[-1, 1] - ordered[0, 1])
        straight = np.hypot(dy, dx)
        m.tortuosity = float(m.skeleton_length_px / straight) if straight > 0 else 1.0

    return m


def build_overlay(img_bgr: np.ndarray,
                  masks: dict[int, np.ndarray],
                  skeletons: dict[int, np.ndarray],
                  alpha: float = 0.4) -> np.ndarray:
    """Наложить маски и скелеты на изображение."""
    overlay = img_bgr.copy()
    for cls_id, mask in masks.items():
        color = ANALYZER_CLASS_COLORS.get(cls_id, (128, 128, 128))
        color_bgr = (color[2], color[1], color[0])
        colored = np.zeros_like(img_bgr)
        colored[mask > 0] = color_bgr
        overlay = cv2.addWeighted(overlay, 1.0, colored, alpha, 0)
    for cls_id, skel in skeletons.items():
        color = ANALYZER_CLASS_COLORS.get(cls_id, (200, 200, 200))
        overlay[skel > 0] = (color[2], color[1], color[0])
    return overlay