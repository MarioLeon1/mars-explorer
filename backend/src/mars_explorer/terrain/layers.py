"""Derived terrain layers from a DEM window: slope, roughness, hillshade, cost and risk.

Everything here is *derived* data resting on explicit assumptions (see :class:`CostModel`).
Limits are illustrative engineering choices, NOT JPL operational values (which are not public).
At 1 m/post the DEM cannot see rocks smaller than roughly a metre — exactly the hazards the
real rover avoids with its own stereo cameras.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float32]

RISK_LABELS = ("low", "moderate", "high", "impassable")


@dataclass(frozen=True, slots=True)
class CostModel:
    """cost per metre = 1 + w_s·(slope/max_slope)² + w_r·(roughness/max_roughness)²;
    cells above either limit, or without data, are impassable."""

    max_slope_deg: float = 30.0
    slope_weight: float = 4.0
    max_roughness_m: float = 0.30
    roughness_weight: float = 3.0
    roughness_window_m: int = 5

    def as_dict(self) -> dict[str, float]:
        return {k: float(v) for k, v in asdict(self).items()}


ASSUMPTIONS = [
    "Slope from the 1 m DEM by central differences; roughness = std of elevation residuals "
    "(DEM minus its local mean) over the roughness window.",
    "Cost per metre = 1 + w_s·(slope/max slope)² + w_r·(roughness/max roughness)²; quadratic so "
    "gentle terrain is nearly free and costs rise steeply near the limits.",
    "Cells beyond either limit, or with no DEM data, are impassable.",
    "Planning cells aggregate 1 m posts conservatively: maximum slope and roughness, mean "
    "elevation.",
    "Default limits (30°, 0.30 m) were calibrated on this DEM so that none of the 708 real "
    "rover localizations falls on an impassable cell (max observed: 28.8°, 0.23 m in a 5 m "
    "neighbourhood). They are engineering assumptions, not JPL's operational values.",
]

LIMITATIONS = [
    "1 m posts miss rocks and steps smaller than about a metre — the hazards the real rover "
    "detects with its own stereo cameras and AutoNav.",
    "No wheel/soil interaction, sand traps, power, communication windows or science goals.",
    "Orbital DEM errors (≈ decimetres) propagate into slope and roughness.",
]


def slope_deg(elevation: Array, cell_m: float) -> Array:
    gy, gx = np.gradient(elevation, cell_m)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)


def _box_mean(values: Array, size: int) -> Array:
    return cv2.blur(values, (size, size), borderType=cv2.BORDER_REFLECT)


def roughness_m(elevation: Array, window: int) -> Array:
    """Std of residuals after removing the local mean; NaN where any input in the window is NaN."""
    valid = np.isfinite(elevation)
    filled = np.where(valid, elevation, 0.0).astype(np.float32)
    weight = _box_mean(valid.astype(np.float32), window)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = _box_mean(filled, window) / weight
        residual = np.where(valid, elevation - mean, 0.0).astype(np.float32)
        variance = _box_mean(residual * residual, window) / weight
    out = np.sqrt(np.maximum(variance, 0.0)).astype(np.float32)
    out[weight < 0.999] = np.nan  # window touches missing data
    return out


def hillshade(
    elevation: Array, cell_m: float, azimuth_deg: float = 315.0, altitude_deg: float = 45.0
) -> Array:
    """Classic Lambertian hillshade in [0, 1] (illumination from the north-west by default)."""
    gy, gx = np.gradient(elevation, cell_m)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)  # gy is along rows (southward), so flip to geographic
    zenith = np.radians(90.0 - altitude_deg)
    azimuth = np.radians(azimuth_deg)
    shade = np.cos(zenith) * np.cos(slope) + np.sin(zenith) * np.sin(slope) * np.cos(
        azimuth - aspect
    )
    return np.clip(shade, 0.0, 1.0).astype(np.float32)


@dataclass(slots=True)
class Traversability:
    """Per-cell layers at one resolution; ``cost`` is +inf where impassable."""

    elevation: Array
    slope: Array
    roughness: Array
    slope_term: Array
    roughness_term: Array
    cost: Array
    risk: NDArray[np.uint8]  # index into RISK_LABELS


def block_reduce(values: Array, factor: int, how: str) -> Array:
    if factor == 1:
        return values
    rows, cols = values.shape[0] // factor, values.shape[1] // factor
    blocks = values[: rows * factor, : cols * factor].reshape(rows, factor, cols, factor)
    with np.errstate(invalid="ignore"):
        if how == "max":
            reduced = np.max(blocks, axis=(1, 3))  # NaN propagates: unknown stays unknown
        elif how == "mean":
            reduced = np.mean(blocks, axis=(1, 3))
        else:
            raise ValueError(how)
    return reduced.astype(np.float32)


PAD_M = 8
"""Extra DEM read around a map so neighbourhood filters never see an artificial border."""


def traversability(
    elevation_1m: Array, model: CostModel, factor: int = 1, pad: int = 0
) -> Traversability:
    """Compute layers on 1 m posts, then aggregate conservatively to ``factor`` m cells.

    ``pad`` metres of real terrain surround the region of interest in ``elevation_1m``; filters
    use them and they are cropped before aggregation (avoids border artefacts in roughness)."""

    def crop(values: Array) -> Array:
        return values[pad : values.shape[0] - pad, pad : values.shape[1] - pad] if pad else values

    slope = block_reduce(crop(slope_deg(elevation_1m, 1.0)), factor, "max")
    rough = block_reduce(crop(roughness_m(elevation_1m, model.roughness_window_m)), factor, "max")
    elevation = block_reduce(crop(elevation_1m), factor, "mean")
    unknown = ~(np.isfinite(slope) & np.isfinite(rough) & np.isfinite(elevation))
    s = np.nan_to_num(slope / model.max_slope_deg, nan=np.inf)
    r = np.nan_to_num(rough / model.max_roughness_m, nan=np.inf)
    slope_term = (model.slope_weight * np.minimum(s, 1.0) ** 2).astype(np.float32)
    rough_term = (model.roughness_weight * np.minimum(r, 1.0) ** 2).astype(np.float32)
    impassable = unknown | (s > 1.0) | (r > 1.0)
    cost = (1.0 + slope_term + rough_term).astype(np.float32)
    cost[impassable] = np.inf
    severity = np.maximum(s, r)
    risk = np.full(cost.shape, 3, np.uint8)
    risk[severity <= 1.0] = 2
    risk[severity < 0.7] = 1
    risk[severity < 0.4] = 0
    risk[impassable] = 3
    return Traversability(elevation, slope, rough, slope_term, rough_term, cost, risk)
