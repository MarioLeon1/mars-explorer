"""Unsupervised texture classes (k-means on per-tile texture statistics).

The classes are ranked from smoothest to most textured. They are NOT geological units: the
same class can contain sand, dust or smooth bedrock, and lighting changes texture strongly.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from mars_explorer.vision.ops import Gray, gradient_magnitude

NOISE_FLOOR = 24.0
"""Added to the tile mean before normalising (8-bit DN). Chosen visually on real Hazcam/Navcam
frames with rover shadows; see docs/perception.md."""


@dataclass(frozen=True, slots=True)
class TextureResult:
    labels: NDArray[np.int32]  # per tile, 0 = smoothest … k-1 = most textured; -1 = ignored
    tile: int
    fractions: list[float]  # share of valid tiles per class
    energy: list[float]  # mean gradient energy per class (ordering key)


def texture_classes(
    gray: Gray,
    *,
    tile: int = 16,
    k: int = 3,
    relative: bool = True,
    noise_floor: float = NOISE_FLOOR,
    seed: int = 7,
) -> TextureResult:
    """Cluster tiles by *relative* texture so that shadow vs. sunlight does not dominate.

    Features per tile, each divided by the tile's mean intensity (coefficient-of-variation
    style, roughly invariant to illumination level): intensity std, mean gradient magnitude,
    mean |Laplacian| (fine-scale roughness). Computed on the original image, because CLAHE's
    local, non-linear stretch would distort the ratios.
    """
    gradient = gradient_magnitude(gray)
    laplacian = np.abs(cv2.Laplacian(cv2.GaussianBlur(gray, (0, 0), 1.0), cv2.CV_32F))
    rows, cols = gray.shape[0] // tile, gray.shape[1] // tile
    if rows == 0 or cols == 0:
        raise ValueError("image smaller than one tile")

    def tiles(values: np.ndarray) -> np.ndarray:
        cropped = values[: rows * tile, : cols * tile].astype(np.float32)
        return cropped.reshape(rows, tile, cols, tile).swapaxes(1, 2).reshape(rows, cols, -1)

    intensity = tiles(gray)
    # Noise floor: dark tiles have low signal but similar sensor noise; without it, shadows
    # would look "rough" purely because noise / small mean is large.
    # With relative=False the raw statistics are used (texture then tracks illumination).
    mean = intensity.mean(axis=2) + noise_floor if relative else np.ones((rows, cols), np.float32)
    features = np.stack(
        [
            intensity.std(axis=2) / mean,
            tiles(gradient).mean(axis=2) / mean,
            tiles(laplacian).mean(axis=2) / mean,
        ],
        axis=2,
    ).reshape(-1, 3)
    raw = tiles(gray)
    # Skip tiles that are mostly saturated (frame padding, blown-out sky); a few clipped
    # pixels inside real terrain must not discard the whole tile.
    unsaturated = ((raw > 2) & (raw < 253)).mean(axis=2)
    valid = (unsaturated > 0.5).reshape(-1)
    labels = np.full(rows * cols, -1, dtype=np.int32)
    if valid.sum() < k:
        return TextureResult(labels.reshape(rows, cols), tile, [0.0] * k, [0.0] * k)

    data = features[valid]
    data = (data - data.mean(axis=0)) / (data.std(axis=0) + 1e-6)
    cv2.setRNGSeed(seed)  # deterministic clustering
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 1e-3)
    _, assigned, _ = cv2.kmeans(
        data.astype(np.float32), k, None, criteria, 5, cv2.KMEANS_PP_CENTERS
    )
    assigned = assigned.reshape(-1)

    gradient_energy = features[valid][:, 1]
    energy = [
        float(gradient_energy[assigned == c].mean()) if np.any(assigned == c) else 0.0
        for c in range(k)
    ]
    order = np.argsort(energy)  # rank clusters: smoothest first
    rank = np.empty(k, dtype=np.int32)
    rank[order] = np.arange(k)
    labels[valid] = rank[assigned]
    counts = np.bincount(labels[valid], minlength=k)
    return TextureResult(
        labels=labels.reshape(rows, cols),
        tile=tile,
        fractions=[float(c / counts.sum()) for c in counts],
        energy=[energy[i] for i in order],
    )
