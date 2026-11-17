"""Rock / obstacle *candidate* detectors.

Two independent classical approaches, so they can be compared against each other and against
human annotations:

* :func:`detect_blobs` — multi-scale Difference-of-Gaussians blob detector (scale-space).
* :func:`detect_contours` — closed edge regions (Canny + morphology + shape filters).

A "candidate" is an image region that *looks like* a compact object. It is not a confirmed rock:
shadows, rover hardware, sand ripples and texture can all trigger it. Sizes are in image
pixels only — a single uncalibrated 2D image gives no physical scale.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from mars_explorer.vision.ops import Gray, canny_auto, clahe, gradient_magnitude, valid_mask


@dataclass(frozen=True, slots=True)
class Candidate:
    x: float  # centre, image px
    y: float
    r: float  # equivalent radius, image px
    score: float
    area_px: float


def non_max_suppression(
    candidates: list[Candidate], overlap: float = 0.8, limit: int | None = None
) -> list[Candidate]:
    """Keep the strongest of candidates whose centres are closer than ``overlap`` × radius.

    Strongest first, so it can stop as soon as ``limit`` candidates are kept. A spatial grid
    limits each check to nearby kept candidates: O(n log n) instead of O(n²), which matters
    when permissive parameters produce tens of thousands of raw responses.
    """
    if not candidates:
        return []
    cell = max(1.0, overlap * max(c.r for c in candidates))
    grid: dict[tuple[int, int], list[Candidate]] = {}
    kept: list[Candidate] = []
    for cand in sorted(candidates, key=lambda c: c.score, reverse=True):
        gx, gy = int(cand.x // cell), int(cand.y // cell)
        neighbours = (
            k for dx in (-1, 0, 1) for dy in (-1, 0, 1) for k in grid.get((gx + dx, gy + dy), ())
        )
        if all(
            math.hypot(cand.x - k.x, cand.y - k.y) > overlap * max(cand.r, k.r) for k in neighbours
        ):
            kept.append(cand)
            grid.setdefault((gx, gy), []).append(cand)
            if limit is not None and len(kept) >= limit:
                break
    return kept


WORK_MAX_SIDE = 1024
"""Detectors run on a copy whose longer side is at most this; results are mapped back."""


def _working_copy(gray: Gray) -> tuple[Gray, float]:
    scale = min(1.0, WORK_MAX_SIDE / max(gray.shape))
    if scale >= 1.0:
        return gray, 1.0
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return resized, scale


def _to_original(candidates: list[Candidate], scale: float) -> list[Candidate]:
    if scale == 1.0:
        return candidates
    return [
        Candidate(c.x / scale, c.y / scale, c.r / scale, c.score, c.area_px / scale**2)
        for c in candidates
    ]


def _is_edge_like(image: np.ndarray, x: int, y: int, ratio: float) -> bool:
    """Hessian test (as in SIFT): reject responses whose principal curvatures differ a lot.

    Shadow boundaries and ridges are elongated (one large curvature, one small); compact
    objects curve similarly in both directions.
    """
    height, width = image.shape
    if not (1 <= x < width - 1 and 1 <= y < height - 1):
        return True
    dxx = image[y, x + 1] + image[y, x - 1] - 2 * image[y, x]
    dyy = image[y + 1, x] + image[y - 1, x] - 2 * image[y, x]
    dxy = (
        image[y + 1, x + 1] - image[y + 1, x - 1] - image[y - 1, x + 1] + image[y - 1, x - 1]
    ) / 4
    trace = dxx + dyy
    det = dxx * dyy - dxy * dxy
    if det <= 0:
        return True  # saddle point or edge
    return float(trace * trace / det) >= (ratio + 1) ** 2 / ratio


def detect_blobs(
    gray: Gray,
    *,
    min_radius: float = 6.0,
    max_radius: float = 60.0,
    levels: int = 8,
    min_strength: float = 0.9,
    edge_ratio: float = 10.0,
    polarity: str = "both",
    margin: float = 0.02,
    roi_top: float = 0.0,
    max_candidates: int = 300,
) -> list[Candidate]:
    """Scale-normalised DoG extrema in (x, y, scale), with SIFT-style edge rejection.

    Radii are in pixels of the input image. Score = |DoG| × σ²/(k−1) ÷ std(CLAHE image):
    a dimensionless "blob contrast" (how strongly the region stands out from its surroundings
    at its own scale). It is NOT a probability.
    """
    work, scale = _working_copy(gray)
    found = _detect_blobs(
        work,
        min_radius=min_radius * scale,
        max_radius=max_radius * scale,
        levels=levels,
        min_strength=min_strength,
        edge_ratio=edge_ratio,
        polarity=polarity,
        margin=margin,
        roi_top=roi_top,
    )
    return _to_original(non_max_suppression(found, limit=max_candidates), scale)


def _detect_blobs(
    gray: Gray,
    *,
    min_radius: float,
    max_radius: float,
    levels: int,
    min_strength: float,
    edge_ratio: float,
    polarity: str,
    margin: float,
    roi_top: float,
) -> list[Candidate]:
    min_radius = max(min_radius, 1.5)
    max_radius = max(max_radius, min_radius * 1.5)
    enhanced = clahe(gray).astype(np.float32)
    spread = float(enhanced.std()) or 1.0
    sigmas = np.geomspace(min_radius / math.sqrt(2), max_radius / math.sqrt(2), levels + 1)
    k = float(sigmas[1] / sigmas[0])
    blurred = [cv2.GaussianBlur(enhanced, (0, 0), float(s)) for s in sigmas]
    responses = np.stack(
        [(blurred[i] - blurred[i + 1]) / (k - 1) / spread for i in range(levels)]
    )  # ≈ σ²∇²G, positive for dark blobs
    if polarity == "bright":
        responses = -responses
    elif polarity == "both":
        responses = np.abs(responses)
    elif polarity != "dark":
        raise ValueError(f"polarity must be bright|dark|both, got {polarity!r}")

    mask = valid_mask(gray, margin, roi_top)
    kernel = np.ones((3, 3), np.uint8)
    spatial_max = np.stack([cv2.dilate(r, kernel) for r in responses])
    candidates: list[Candidate] = []
    for i in range(levels):
        neighbours = [spatial_max[j] for j in (i - 1, i, i + 1) if 0 <= j < levels]
        peak = (responses[i] >= np.max(neighbours, axis=0)) & (responses[i] >= min_strength)
        peak &= mask
        ys, xs = np.nonzero(peak)
        radius = float(sigmas[i] * math.sqrt(2))
        for y, x in zip(ys, xs, strict=True):
            if edge_ratio > 0 and _is_edge_like(blurred[i], int(x), int(y), edge_ratio):
                continue
            candidates.append(
                Candidate(
                    float(x), float(y), radius, float(responses[i, y, x]), math.pi * radius**2
                )
            )
    return candidates


def detect_contours(
    gray: Gray,
    *,
    min_area: float = 120.0,
    max_area: float = 20000.0,
    min_solidity: float = 0.75,
    max_aspect: float = 3.0,
    close_px: int = 5,
    min_edge_strength: float = 1.8,
    margin: float = 0.02,
    roi_top: float = 0.0,
    max_candidates: int = 300,
) -> list[Candidate]:
    """Compact regions enclosed by edges. Areas are in pixels² of the input image.

    Score = mean gradient magnitude along the region outline ÷ median gradient of the image:
    how much sharper the outline is than typical texture. Dimensionless, NOT a probability.
    """
    work, scale = _working_copy(gray)
    found = _detect_contours(
        work,
        min_area=min_area * scale**2,
        max_area=max_area * scale**2,
        min_solidity=min_solidity,
        max_aspect=max_aspect,
        close_px=close_px,
        min_edge_strength=min_edge_strength,
        margin=margin,
        roi_top=roi_top,
    )
    return _to_original(non_max_suppression(found, limit=max_candidates), scale)


def _detect_contours(
    gray: Gray,
    *,
    min_area: float,
    max_area: float,
    min_solidity: float,
    max_aspect: float,
    close_px: int,
    min_edge_strength: float,
    margin: float,
    roi_top: float,
) -> list[Candidate]:
    enhanced = clahe(gray)
    edges = canny_auto(enhanced)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_px, close_px))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)

    gradient = gradient_magnitude(enhanced)
    reference = float(np.median(gradient[gradient > 0])) if np.any(gradient > 0) else 1.0
    mask = valid_mask(gray, margin, roi_top)
    candidates: list[Candidate] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not min_area <= area <= max_area:
            continue
        hull_area = float(cv2.contourArea(cv2.convexHull(contour)))
        if hull_area <= 0 or area / hull_area < min_solidity:
            continue
        (_, _), (w, h), _ = cv2.minAreaRect(contour)
        if min(w, h) <= 0 or max(w, h) / min(w, h) > max_aspect:
            continue
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            continue
        cx, cy = moments["m10"] / moments["m00"], moments["m01"] / moments["m00"]
        if not mask[int(cy), int(cx)]:
            continue
        outline = contour[:, 0, :]
        strength = float(gradient[outline[:, 1], outline[:, 0]].mean()) / reference
        if strength < min_edge_strength:
            continue
        candidates.append(Candidate(cx, cy, math.sqrt(area / math.pi), strength, area))
    return candidates
