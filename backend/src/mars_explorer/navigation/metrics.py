"""Route evaluation on a common footing, and deterministic (template-based) explanations.

Every route — from any planner, or the rover's real traverse — is re-sampled every half cell and
scored against the same layers. Costs reported to the user therefore compare like with like, even
though each planner optimises slightly differently internally.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import cv2
import numpy as np

from mars_explorer.navigation.grid import Point
from mars_explorer.terrain.layers import Traversability

PROFILE_POINTS = 160


@dataclass(slots=True)
class RouteMetrics:
    feasible: bool
    length_m: float
    impassable_m: float  # length crossing cells the model calls impassable
    cost: float
    cost_distance: float  # the "1 ×" part of cost per metre
    cost_slope: float
    cost_roughness: float
    max_slope_deg: float
    mean_slope_deg: float
    max_roughness_m: float
    elevation_gain_m: float
    elevation_loss_m: float
    min_clearance_m: float | None  # distance to the nearest impassable cell
    profile: list[tuple[float, float]]  # (distance m, elevation m)


def clearance_map(layers: Traversability, cell_m: float) -> np.ndarray:
    passable = np.isfinite(layers.cost).astype(np.uint8)
    if passable.all():
        return np.full(passable.shape, np.inf, np.float32)
    return cv2.distanceTransform(passable, cv2.DIST_L2, 5).astype(np.float32) * cell_m


def evaluate(
    path: list[Point], layers: Traversability, cell_m: float, clearance: np.ndarray
) -> RouteMetrics:
    rows, cols = layers.cost.shape
    samples_r: list[float] = []
    samples_c: list[float] = []
    seg_len: list[float] = []
    for a, b in itertools.pairwise(path):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, math.ceil(length * 2))
        for k in range(n):
            t = (k + 0.5) / n
            samples_r.append(a[0] + (b[0] - a[0]) * t)
            samples_c.append(a[1] + (b[1] - a[1]) * t)
            seg_len.append(length / n * cell_m)
    if not samples_r:
        return RouteMetrics(False, 0, 0, math.inf, 0, 0, 0, 0, 0, 0, 0, 0, None, [])
    r = np.clip(np.rint(samples_r).astype(np.intp), 0, rows - 1)
    c = np.clip(np.rint(samples_c).astype(np.intp), 0, cols - 1)
    w = np.asarray(seg_len)
    cost = layers.cost[r, c]
    blocked = ~np.isfinite(cost)
    feasible = not bool(blocked.any())
    slope = layers.slope[r, c]
    rough = layers.roughness[r, c]
    elevation = layers.elevation[r, c].astype(np.float64)
    distance = np.cumsum(w) - w / 2
    rises = np.diff(elevation)
    step = max(1, len(distance) // PROFILE_POINTS)
    clear = clearance[r, c]
    return RouteMetrics(
        feasible=feasible,
        length_m=float(w.sum()),
        impassable_m=float(w[blocked].sum()),
        cost=float((cost * w).sum()) if feasible else math.inf,
        cost_distance=float(w.sum()),
        cost_slope=float((layers.slope_term[r, c] * w).sum()),
        cost_roughness=float((layers.roughness_term[r, c] * w).sum()),
        max_slope_deg=float(np.nanmax(slope)),
        mean_slope_deg=float(np.nanmean(slope)),
        max_roughness_m=float(np.nanmax(rough)),
        elevation_gain_m=float(rises[rises > 0].sum()) if len(rises) else 0.0,
        elevation_loss_m=float(-rises[rises < 0].sum()) if len(rises) else 0.0,
        min_clearance_m=float(clear.min()) if np.isfinite(clear.min()) else None,
        profile=[
            (round(float(d), 1), round(float(z), 2))
            for d, z in zip(distance[::step], elevation[::step], strict=True)
        ],
    )


TITLES = {
    "astar": "A*",
    "dijkstra": "Dijkstra",
    "theta_star": "Theta*",
    "rrt_star": "RRT*",
    "actual": "Rover's actual drive",
}


def _pct(a: float, b: float) -> str:
    return f"{(a / b - 1) * 100:+.0f} %" if b else "—"


def explain(
    metrics: dict[str, RouteMetrics],
    expanded: dict[str, int],
    max_slope_limit: float,
    rrt_seed: int | None,
) -> tuple[str | None, list[str]]:
    """Pick the best feasible plan (lowest total cost) and explain the comparison in plain words.
    Template-based and deterministic — no language model is involved."""
    plans = {k: m for k, m in metrics.items() if k != "actual" and m.feasible}
    if not plans:
        return None, ["No planner found a feasible route under this cost model."]
    best_key = min(plans, key=lambda k: plans[k].cost)
    best = plans[best_key]
    lines = [
        f"{TITLES[best_key]} has the lowest total cost ({best.cost:.0f}) "
        f"over {best.length_m:.0f} m: "
        f"{best.cost_distance:.0f} for distance, {best.cost_slope:.0f} slope penalty, "
        f"{best.cost_roughness:.0f} roughness penalty.",
        f"Its steepest point is {best.max_slope_deg:.1f}° (limit {max_slope_limit:.0f}°); "
        "it climbs "
        f"{best.elevation_gain_m:.0f} m and descends {best.elevation_loss_m:.0f} m.",
    ]
    a, d = plans.get("astar"), plans.get("dijkstra")
    if a and d:
        same = abs(a.cost - d.cost) <= 1e-6 * max(1.0, a.cost)
        ratio = expanded.get("dijkstra", 0) / max(1, expanded.get("astar", 1))
        verdict = "reach the same optimal grid cost" if same else "differ slightly in cost"
        lines.append(
            f"A* and Dijkstra {verdict}; "
            f"A* expanded {expanded.get('astar', 0):,} nodes vs {expanded.get('dijkstra', 0):,} "
            f"({ratio:.1f}× fewer) thanks to its admissible heuristic."
        )
    t = plans.get("theta_star")
    grid_ref = a or d
    if t and grid_ref:
        lines.append(
            f"Theta* is {_pct(t.length_m, grid_ref.length_m)} in length and "
            f"{_pct(t.cost, grid_ref.cost)} "
            "in cost versus the 8-connected grid path: any-angle segments remove the 45° staircase."
        )
    r = plans.get("rrt_star")
    if r:
        lines.append(
            f"RRT* (seed {rrt_seed}) is randomised and only asymptotically optimal: its cost is "
            f"{_pct(r.cost, best.cost)} versus the best plan. Change the seed to see the variance."
        )
    elif "rrt_star" in metrics:
        lines.append("RRT* did not produce a feasible route with this seed and iteration budget.")
    actual = metrics.get("actual")
    if actual:
        if actual.feasible:
            lines.append(
                f"The rover's real drive path (JPL MMGIS, ~1 m vertices) scores {actual.cost:.0f} "
                f"under this model ({_pct(actual.cost, best.cost)} vs. the best plan; "
                f"{actual.length_m:.0f} m). Differences are expected: the team planned with "
                "rover-scale stereo hazard maps, science targets and operational constraints that "
                "this orbital model does not have."
            )
        else:
            lines.append(
                f"The rover's real drive path crosses {actual.impassable_m:.0f} m of cells this "
                "model calls impassable. The rover drove there, so the model is too strict at "
                "those spots "
                "(or the 1 m DEM has artefacts) — a limit of the model, not of the rover."
            )
    return best_key, lines
