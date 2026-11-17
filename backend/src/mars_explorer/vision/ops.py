"""Basic image operations (pure functions on NumPy arrays, uint8 grayscale unless stated)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

Gray = NDArray[np.uint8]
Float = NDArray[np.float32]


class ImageReadError(ValueError):
    pass


def load_gray(path: Path) -> Gray:
    """Read any JPEG/PNG as 8-bit grayscale (colour Mastcam-Z frames are converted)."""
    data = np.fromfile(path, dtype=np.uint8)  # handles non-ASCII Windows paths
    image = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ImageReadError(f"cannot decode image {path}")
    return image


def clahe(gray: Gray, clip_limit: float = 2.0, tiles: int = 8) -> Gray:
    """Contrast-Limited Adaptive Histogram Equalisation: local contrast, limited noise boost."""
    return cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tiles, tiles)).apply(gray)


def canny_auto(gray: Gray, sigma: float = 0.33, blur: float = 1.2) -> Gray:
    """Canny with thresholds derived from the median intensity (no per-image hand tuning)."""
    smoothed = cv2.GaussianBlur(gray, (0, 0), blur) if blur > 0 else gray
    median = float(np.median(smoothed))
    low = int(max(0, (1.0 - sigma) * median))
    high = int(min(255, (1.0 + sigma) * median))
    return cv2.Canny(smoothed, low, max(high, low + 1))


def gradient_magnitude(gray: Gray, blur: float = 1.0) -> Float:
    smoothed = cv2.GaussianBlur(gray, (0, 0), blur) if blur > 0 else gray
    gx = cv2.Sobel(smoothed, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smoothed, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def to_uint8(values: Float) -> Gray:
    """Scale a float map to 0-255 using its 99th percentile (robust to a few hot pixels)."""
    top = float(np.percentile(values, 99)) or 1.0
    return np.clip(values * (255.0 / top), 0, 255).astype(np.uint8)


def valid_mask(gray: Gray, margin: float, roi_top: float) -> NDArray[np.bool_]:
    """Pixels considered for detection: away from borders and below an optional top band."""
    height, width = gray.shape
    mask = np.zeros((height, width), dtype=bool)
    m_y, m_x = int(height * margin), int(width * margin)
    top = max(m_y, int(height * roi_top))
    mask[top : height - m_y, m_x : width - m_x] = True
    # Saturated black/white areas (frame borders, subframe padding) carry no texture.
    mask &= (gray > 2) & (gray < 253)
    return mask
