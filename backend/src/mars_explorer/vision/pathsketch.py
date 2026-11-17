"""Image-space path sketch: a route drawn *on one raw image* that avoids rock candidates.

What it is
    A deterministic, explainable illustration of the idea behind hazard avoidance: detected
    rock *candidates* (blob or contour detector) become no-go discs, inflated by a clearance
    factor; image texture adds a soft "roughness" cost; the sky above the horizon is excluded.
    Lazy Theta* (the same planner used on the orbital DEM) then finds the cheapest any-angle
    path between two points of the image.

What it is NOT (integrity rules 4 and 6)
    * Not a metric route: costs and lengths are in image pixels. A single uncalibrated 2D
      image has no scale, and perspective compresses distant terrain into a few rows.
    * Not what the rover would drive: Perseverance's AutoNav plans on 3D terrain maps built
      from stereo pairs, with its real wheel geometry and vehicle limits.
    * Not a rock map: candidates are algorithmic detections, not confirmed rocks.
    The language model is never involved; the result is reproducible from its parameters.
"""

from __future__ import annotations

import base64
import itertools
import math
import time
from dataclasses import dataclass, field
from typing import Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from mars_explorer.navigation.grid import PlanningGrid
from mars_explorer.navigation.planners import astar, lazy_theta_star
from mars_explorer.vision.ops import Gray, gradient_magnitude
from mars_explorer.vision.rocks import Candidate, detect_blobs, detect_contours

Detector = Literal["blobs", "contours"]

CELL_TARGET = 128
"""Grid columns: the longer image side is divided into about this many cells."""
HALO_COST = 3.0
"""Extra cost per cell in the soft halo just outside each inflated obstacle."""
HORIZON_MAX = 0.75

ASSUMPTIONS = [
    "Rock candidates (algorithmic) are treated as obstacles, inflated by the clearance factor "
    "times their radius in pixels; a soft halo around them is discouraged, not forbidden.",
    "Rougher image texture costs more (relative gradient energy, 0–1 per cell, times the "
    "roughness weight). Smooth sand and flat rock cost little.",
    "Everything above the horizon line, and saturated/padded areas, is excluded.",
    "Start defaults to the bottom centre of the image (the ground nearest the camera).",
]
LIMITATIONS = [
    "Image-space only: lengths are pixels, not metres. Perspective makes far obstacles small "
    "and squeezes far terrain into few rows, so the path's shape is not its real geometry.",
    "Not a drivable route. Perseverance plans on 3D terrain maps from stereo images "
    "(AutoNav), using its real size, wheel geometry and tilt limits.",
    "Candidates can be shadows, hardware or texture, and small or low-contrast rocks can be "
    "missed. Slopes, sand traps and drop-offs are invisible to this method.",
    "Rover hardware in the frame (wheels, deck, the rover's shadow) is not recognised as an "
    "obstacle: in Hazcam images place the start (A) on open ground.",
]


@dataclass(frozen=True, slots=True)
class SketchParams:
    detector: Detector = "blobs"
    clearance: float = 1.6
    roughness_weight: float = 2.0
    horizon: float | None = None  # fraction of image height; None = estimate automatically


@dataclass(slots=True)
class PathSketch:
    width: int
    height: int
    found: bool
    reason: str | None
    path: list[tuple[float, float]]  # (x, y) image px
    start: tuple[float, float]
    goal: tuple[float, float]
    horizon: float
    horizon_auto: bool
    obstacles: list[Candidate]
    cell_px: float
    grid_shape: tuple[int, int]
    length_px: float
    straight_px: float
    min_clearance_px: float | None
    blocking_straight: int
    elapsed_ms: float
    cost_png: bytes
    explanation: list[str] = field(default_factory=list)


def estimate_horizon(gray: Gray) -> float:
    """Fraction of the image height where textured ground starts (0 when there is no sky).

    Sky in raw Navcam/Hazcam frames is smooth: rows above the horizon have far less gradient
    energy than ground rows. The horizon is the first row (from the top) whose smoothed energy
    reaches 35 % of the median energy of the lower half of the image."""
    energy = gradient_magnitude(gray, blur=1.5).mean(axis=1)
    if energy.size < 8:
        return 0.0
    width = max(3, energy.size // 50) | 1
    smooth = np.convolve(energy, np.ones(width) / width, mode="same")
    reference = float(np.median(smooth[energy.size // 2 :]))
    if reference <= 0:
        return 0.0
    limit = int(energy.size * HORIZON_MAX)
    for row in range(limit):
        if smooth[row] >= 0.35 * reference:
            return round(row / energy.size, 3)
    return HORIZON_MAX


def _cell_texture(gray: Gray, rows: int, cols: int) -> NDArray[np.float32]:
    """Relative gradient energy per cell, scaled to 0..1 by its 95th percentile."""
    gradient = gradient_magnitude(gray, blur=1.0) / (
        cv2.GaussianBlur(gray, (0, 0), 4).astype(np.float32) + 24.0
    )
    cells = cv2.resize(gradient, (cols, rows), interpolation=cv2.INTER_AREA)
    top = float(np.percentile(cells, 95)) or 1.0
    return np.clip(cells / top, 0.0, 1.0).astype(np.float32)


def _segment_hits(candidate: Candidate, a: tuple[float, float], b: tuple[float, float]) -> bool:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = (
        0.0
        if length2 == 0
        else max(0.0, min(1.0, ((candidate.x - ax) * dx + (candidate.y - ay) * dy) / length2))
    )
    return math.hypot(ax + t * dx - candidate.x, ay + t * dy - candidate.y) <= candidate.r


def _cost_png(cost: NDArray[np.float32], core: NDArray[np.bool_]) -> bytes:
    """RGBA overlay at grid resolution: red = excluded, amber = obstacle halo / rough terrain."""
    rows, cols = cost.shape
    rgba = np.zeros((rows, cols, 4), np.uint8)
    blocked = ~np.isfinite(cost)
    finite = np.where(blocked, 1.0, cost)
    extra = np.clip((finite - 1.0) / (1.0 + HALO_COST), 0.0, 1.0)
    rgba[..., 0] = 230
    rgba[..., 1] = (170 * (1 - extra)).astype(np.uint8)
    rgba[..., 2] = 40
    rgba[..., 3] = (extra * 120).astype(np.uint8)
    rgba[blocked] = (229, 83, 75, 110)
    rgba[core] = (229, 83, 75, 190)
    ok, encoded = cv2.imencode(".png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return encoded.tobytes()


def sketch_path(
    gray: Gray,
    goal: tuple[float, float],
    start: tuple[float, float] | None = None,
    params: SketchParams | None = None,
) -> PathSketch:
    """Plan an image-space path from ``start`` to ``goal`` (fractions of width/height)."""
    params = params or SketchParams()
    started = time.perf_counter()
    height, width = gray.shape
    horizon_auto = params.horizon is None
    horizon = estimate_horizon(gray) if params.horizon is None else min(params.horizon, HORIZON_MAX)

    detect = detect_blobs if params.detector == "blobs" else detect_contours
    obstacles = [c for c in detect(gray, roi_top=horizon) if c.y >= horizon * height]

    cell_px = max(height, width) / CELL_TARGET
    rows, cols = max(2, round(height / cell_px)), max(2, round(width / cell_px))
    cost = 1.0 + params.roughness_weight * _cell_texture(gray, rows, cols)

    # Excluded: sky and saturated/padded regions.
    cost[: math.ceil(horizon * rows), :] = np.inf
    saturated = ((gray <= 2) | (gray >= 253)).astype(np.float32)
    cost[cv2.resize(saturated, (cols, rows), interpolation=cv2.INTER_AREA) > 0.5] = np.inf

    yy, xx = np.mgrid[0:rows, 0:cols]
    centres_x, centres_y = (xx + 0.5) * width / cols, (yy + 0.5) * height / rows
    core = np.zeros((rows, cols), bool)
    for c in obstacles:
        distance = np.hypot(centres_x - c.x, centres_y - c.y)
        inflated = c.r * params.clearance + cell_px * 0.5
        core |= distance <= c.r
        cost[distance <= inflated] = np.inf
        halo = (distance > inflated) & (distance <= inflated + max(c.r, 2 * cell_px))
        cost[halo] += HALO_COST

    grid = PlanningGrid(cost.astype(np.float32), cell_m=1.0)

    def to_cell(point: tuple[float, float]) -> tuple[int, int]:
        x, y = point
        return (min(rows - 1, max(0, int(y * rows))), min(cols - 1, max(0, int(x * cols))))

    start_frac = start or (0.5, 0.96)
    start_cell = grid.nearest_passable(to_cell(start_frac), max_radius=10)
    goal_cell = grid.nearest_passable(to_cell(goal), max_radius=10)
    to_px = lambda cell: ((cell[1] + 0.5) * width / cols, (cell[0] + 0.5) * height / rows)  # noqa: E731
    start_px = to_px(start_cell) if start_cell else (start_frac[0] * width, start_frac[1] * height)
    goal_px = to_px(goal_cell) if goal_cell else (goal[0] * width, goal[1] * height)
    straight = math.dist(start_px, goal_px)
    blocking = sum(1 for c in obstacles if _segment_hits(c, start_px, goal_px))

    reason: str | None = None
    path: list[tuple[float, float]] = []
    if start_cell is None:
        reason = "the start is inside an obstacle or above the horizon, with no free ground nearby"
    elif goal_cell is None:
        reason = "the goal is inside an obstacle or above the horizon, with no free ground nearby"
    else:
        result = lazy_theta_star(grid, start_cell, goal_cell)
        if not result.found:
            result = astar(grid, start_cell, goal_cell)
        if result.found:
            path = [((c + 0.5) * width / cols, (r + 0.5) * height / rows) for r, c in result.path]
        else:
            reason = result.reason or "no free corridor between start and goal"

    length = sum(math.dist(a, b) for a, b in itertools.pairwise(path)) if path else 0.0
    clearance = None
    if path and obstacles:
        samples = []
        for a, b in itertools.pairwise(path):
            n = max(2, int(math.dist(a, b) / 2))
            samples += [
                (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t) for t in np.linspace(0, 1, n)
            ]
        clearance = min(math.hypot(x - c.x, y - c.y) - c.r for x, y in samples for c in obstacles)

    sketch = PathSketch(
        width=width,
        height=height,
        found=bool(path),
        reason=reason,
        path=path,
        start=start_px,
        goal=goal_px,
        horizon=horizon,
        horizon_auto=horizon_auto,
        obstacles=obstacles,
        cell_px=cell_px,
        grid_shape=(rows, cols),
        length_px=length,
        straight_px=straight,
        min_clearance_px=None if clearance is None else max(0.0, clearance),
        blocking_straight=blocking,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        cost_png=_cost_png(cost, core),
    )
    sketch.explanation = explain(sketch, params)
    return sketch


def explain(sketch: PathSketch, params: SketchParams) -> list[str]:
    detector = "blob (DoG)" if params.detector == "blobs" else "contour"
    lines = [
        f"{len(sketch.obstacles)} rock candidates from the {detector} detector were treated as "
        f"obstacles (inflated ×{params.clearance:g}).",
    ]
    if not sketch.found:
        lines.append(f"No path: {sketch.reason}.")
        return lines
    detour = (sketch.length_px / sketch.straight_px - 1) * 100 if sketch.straight_px else 0.0
    if sketch.blocking_straight:
        lines.append(
            f"The straight line from A to B crosses {sketch.blocking_straight} candidate(s); "
            f"the path bends around them, {detour:.0f} % longer than the straight line (in pixels)."
        )
    else:
        lines.append(
            "No candidate lies on the straight line from A to B; any bend comes from avoiding "
            f"halos and rough texture ({detour:.0f} % longer than straight, in pixels)."
        )
    if sketch.min_clearance_px is not None:
        lines.append(
            f"Closest approach to a candidate's edge: {sketch.min_clearance_px:.0f} px "
            "(image pixels, not a physical distance)."
        )
    lines.append(
        "Horizon "
        + ("estimated automatically" if sketch.horizon_auto else "set by you")
        + f" at {sketch.horizon * 100:.0f} % of the image height; nothing above it is used."
    )
    return lines


def png_data_url(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
