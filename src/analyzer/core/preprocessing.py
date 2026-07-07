from __future__ import annotations
import cv2
import numpy as np


def ensure_bgr(img: np.ndarray) -> np.ndarray:
    if img is None:
        return None
    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img.copy()


def compute_laplacian_variance(gray: np.ndarray) -> float:
    """Оценка резкости кадра (чем выше — тем чётче)."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def apply_clahe(img_bgr: np.ndarray,
                clip_limit: float = 2.0,
                tile_grid: int = 8) -> np.ndarray:
    """CLAHE на канале L в LAB-пространстве."""
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit,
                            tileGridSize=(tile_grid, tile_grid))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def apply_auto_windowing(img_bgr: np.ndarray,
                         low_pct: float = 1.0,
                         high_pct: float = 99.0) -> np.ndarray:
    """Авто-windowing: обрезаем 1% хвосты гистограммы."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    lo = np.percentile(gray, low_pct)
    hi = np.percentile(gray, high_pct)
    if hi == lo:
        return img_bgr
    lut = np.clip((gray.astype(np.float32) - lo) / (hi - lo) * 255,
                  0, 255).astype(np.uint8)
    return cv2.cvtColor(lut, cv2.COLOR_GRAY2BGR)


def apply_frangi_filter(img_bgr: np.ndarray,
                        sigmas: tuple = (1, 3, 5)) -> np.ndarray:
    """Vesselness filter (Frangi) — выделяет трубчатые структуры."""
    from skimage.filters import frangi
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY).astype(np.float64) / 255.0
    vessel = frangi(gray, sigmas=sigmas, black_ridges=False)
    vessel_norm = cv2.normalize(vessel, None, 0, 255,
                                cv2.NORM_MINMAX).astype(np.uint8)
    return cv2.cvtColor(vessel_norm, cv2.COLOR_GRAY2BGR)


def adjust_brightness_contrast(img_bgr: np.ndarray,
                                brightness: int = 0,
                                contrast: int = 0,
                                gamma: float = 1.0) -> np.ndarray:
    result = img_bgr.astype(np.float32)
    if contrast != 0:
        f = (259 * (contrast + 255)) / (255 * (259 - contrast))
        result = f * (result - 128) + 128
    result = np.clip(result + brightness, 0, 255)
    if gamma != 1.0:
        inv = 1.0 / max(gamma, 0.01)
        table = np.array([((i / 255.0) ** inv) * 255
                          for i in range(256)]).astype(np.uint8)
        return cv2.LUT(np.clip(result, 0, 255).astype(np.uint8), table)
    return np.clip(result, 0, 255).astype(np.uint8)


def apply_preprocessing(img_bgr: np.ndarray, params: dict) -> np.ndarray:
    """Применить все настройки предобработки из словаря params."""
    proc = img_bgr.copy()
    if params.get("auto_window"):
        proc = apply_auto_windowing(proc)
    if params.get("clahe"):
        proc = apply_clahe(proc,
                           clip_limit=params.get("clahe_clip", 2.0),
                           tile_grid=params.get("clahe_tile", 8))
    proc = adjust_brightness_contrast(
        proc,
        brightness=params.get("brightness", 0),
        contrast=params.get("contrast", 0),
        gamma=params.get("gamma", 1.0),
    )
    return proc