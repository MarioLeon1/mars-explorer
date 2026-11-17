"""Synthetic test scenes with KNOWN ground truth (the only way to test detectors objectively).

These are clearly artificial and are never shown in the app or mixed with mission data.
"""

from __future__ import annotations

import cv2
import numpy as np

ROCKS: list[tuple[int, int, int]] = [  # (x, y, radius) in px
    (120, 140, 14),
    (330, 220, 20),
    (520, 120, 10),
    (210, 380, 24),
    (480, 400, 16),
    (650, 300, 18),
]
SIZE = (480, 760)  # height, width


def rock_scene(seed: int = 3, with_shadow_edge: bool = True) -> np.ndarray:
    """Grey textured ground, lit rocks with cast shadows and (optionally) a long straight
    shadow boundary like the rover's own shadow."""
    rng = np.random.default_rng(seed)
    height, width = SIZE
    image = np.full((height, width), 120, np.float32)
    image += cv2.GaussianBlur(rng.normal(0, 8, (height, width)).astype(np.float32), (0, 0), 1.2)
    if with_shadow_edge:
        image[: height // 5, :] -= 55  # long horizontal shadow band across the top
    for x, y, r in ROCKS:
        cv2.circle(image, (x + r // 2, y + r // 2), r, 70, -1)  # cast shadow (down-right)
        cv2.circle(image, (x, y), r, 200, -1)  # lit rock face
    image = cv2.GaussianBlur(image, (0, 0), 1.0)
    return np.clip(image, 0, 255).astype(np.uint8)


def encode(image: np.ndarray, ext: str = ".jpg") -> bytes:
    ok, data = cv2.imencode(ext, image)
    assert ok
    return data.tobytes()


def textured_pair(shift: int = 20, seed: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """A perfectly rectified "stereo pair" of a flat random texture.

    As in a real left/right pair, scene content appears ``shift`` px further LEFT in the right
    image, so disparity (right − left) is −shift.
    """
    rng = np.random.default_rng(seed)
    base = cv2.GaussianBlur(rng.integers(0, 255, (400, 640)).astype(np.uint8), (0, 0), 1.5)
    base = cv2.equalizeHist(base)
    left = base[:, : base.shape[1] - shift]
    right = base[:, shift:]
    return left.copy(), right.copy()
