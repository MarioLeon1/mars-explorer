"""Terrain maps and route planning over the real PLACES DEM.

A *map* is a square region of interest (ROI) cut from the 1 m DEM, with derived layers and a
planning grid. Maps are identified by a hash of their inputs and kept in a small in-memory LRU
(layers are also written as PNG). Plan requests carry the map parameters, so a restart never
breaks a plan: the map is simply rebuilt.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy import Engine
from sqlmodel import Session, select

from mars_explorer.core.config import Settings
from mars_explorer.core.errors import InvalidRequestError, NoDataError, NotFoundError
from mars_explorer.db.models import TraverseSegment, Waypoint
from mars_explorer.navigation.grid import PlanningGrid, Point
from mars_explorer.navigation.metrics import TITLES, RouteMetrics, clearance_map, evaluate, explain
from mars_explorer.navigation.planners import PlanResult, astar, lazy_theta_star, rrt_star
from mars_explorer.terrain import TERRAIN_VERSION
from mars_explorer.terrain.dem import PLACES_DEM, Dem, DemSpec, en_to_lonlat
from mars_explorer.terrain.layers import (
    ASSUMPTIONS,
    LIMITATIONS,
    PAD_M,
    RISK_LABELS,
    CostModel,
    Traversability,
    hillshade,
    roughness_m,
    slope_deg,
    traversability,
)

log = logging.getLogger(__name__)

MIN_SIZE_M = 100
MAX_SIZE_M = 3000
MAX_GRID_SIDE = 300  # planning cells per side (keeps pure-Python planners interactive)
DISPLAY_SIDE = 1200  # pixels per side of display layers
OVERVIEW_FACTOR = 10  # metres per pixel of the whole-DEM overview
PLANNERS = ("astar", "dijkstra", "theta_star", "rrt_star")
SNAP_RADIUS_CELLS = 6

# Colours (RGB) — status palette for risk (state), single-hue ramps for magnitudes.
RISK_COLOURS = [(95, 191, 122, 0), (224, 179, 65, 110), (230, 126, 60, 160), (229, 83, 75, 200)]
SLOPE_RAMP = ((40, 26, 20), (217, 102, 58), (250, 215, 190))
ROUGH_RAMP = ((14, 36, 40), (92, 200, 214), (220, 245, 248))


@dataclass(slots=True)
class TerrainMap:
    id: str
    center_e: float
    center_n: float
    size_m: int
    cell_m: int  # planning cell size
    e_min: float
    n_max: float
    model: CostModel
    layers: Traversability
    clearance: np.ndarray
    legends: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)

    @property
    def e_max(self) -> float:
        return self.e_min + self.size_m

    @property
    def n_min(self) -> float:
        return self.n_max - self.size_m

    def to_cell(self, easting: float, northing: float) -> Point:
        return (
            (self.n_max - northing) / self.cell_m - 0.5,
            (easting - self.e_min) / self.cell_m - 0.5,
        )

    def to_en(self, point: Point) -> tuple[float, float]:
        row, col = point
        return self.e_min + (col + 0.5) * self.cell_m, self.n_max - (row + 0.5) * self.cell_m


@dataclass(slots=True)
class RouteOut:
    planner: str
    found: bool
    reason: str | None
    points: list[tuple[float, float]]
    metrics: RouteMetrics | None
    expanded: int
    elapsed_ms: float
    extra: dict[str, float | int]


@dataclass(slots=True)
class PlanOut:
    map: TerrainMap
    start: tuple[float, float]
    goal: tuple[float, float]
    snapped: bool
    routes: list[RouteOut]
    actual: RouteOut | None
    best: str | None
    explanation: list[str]


def _ramp(
    values: np.ndarray, vmax: float, stops: tuple[tuple[int, int, int], ...], alpha: int
) -> np.ndarray:
    t = np.clip(np.nan_to_num(values / vmax, nan=0.0), 0.0, 1.0)
    lo, mid, hi = (np.array(s, np.float32) for s in stops)
    first = t[..., None] < 0.5
    u = t[..., None] * 2
    rgb = np.where(first, lo + (mid - lo) * u, mid + (hi - mid) * (u - 1))
    rgba = np.empty((*values.shape, 4), np.uint8)
    rgba[..., :3] = rgb.astype(np.uint8)
    rgba[..., 3] = np.where(np.isnan(values), 0, alpha)
    return rgba


def _hex(rgb: tuple[int, ...]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb[:3])


def _write_png(path: Path, rgba: np.ndarray) -> None:
    ok, data = cv2.imencode(".png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    if not ok:
        raise RuntimeError(f"PNG encoding failed for {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(data.tobytes())
    os.replace(tmp, path)


def _simplify(path: list[Point]) -> list[Point]:
    """Drop vertices that lie on a straight continuation (grid paths have many)."""
    if len(path) < 3:
        return path
    out = [path[0]]
    for prev, here, nxt in zip(path, path[1:], path[2:], strict=False):
        cross = (here[0] - prev[0]) * (nxt[1] - here[1]) - (here[1] - prev[1]) * (nxt[0] - here[0])
        if abs(cross) > 1e-9:
            out.append(here)
    out.append(path[-1])
    return out


class TerrainService:
    def __init__(self, settings: Settings, engine: Engine, spec: DemSpec = PLACES_DEM) -> None:
        self._settings = settings
        self._engine = engine
        self._spec = spec
        self._dem: Dem | None = None
        self._maps: OrderedDict[str, TerrainMap] = OrderedDict()
        self._lock = threading.Lock()

    # ---- DEM availability --------------------------------------------------------------

    @property
    def dem_path(self) -> Path:
        return self._settings.terrain_dir / "m20_orbital_dem.img"

    @property
    def available(self) -> bool:
        return self.dem_path.is_file() and self.dem_path.stat().st_size == self._spec.nbytes

    @property
    def dem(self) -> Dem:
        if self._dem is None:
            if not self.available:
                raise NoDataError(
                    "The orbital DEM is not downloaded yet. "
                    "Run: cd backend; uv run mars-terrain fetch",
                    code="terrain_not_available",
                )
            self._dem = Dem(self.dem_path, self._spec)
        return self._dem

    @property
    def derived_dir(self) -> Path:
        return self._settings.data_dir / "derived" / "terrain"

    # ---- whole-DEM products --------------------------------------------------------------

    def overview_path(self) -> Path:
        path = self.derived_dir / f"overview_v{TERRAIN_VERSION}.png"
        if not path.is_file():
            elevation = self.dem.overview(OVERVIEW_FACTOR)
            shade = (hillshade(elevation, float(OVERVIEW_FACTOR)) * 215 + 25).astype(np.uint8)
            rgba = np.dstack(
                [shade, shade, shade, np.where(np.isnan(elevation), 0, 255).astype(np.uint8)]
            )
            _write_png(path, rgba)
        return path

    def validation(self) -> dict[str, Any]:
        """Compare JPL waypoint elevations with the DEM: a check of the georeferencing."""
        with Session(self._engine) as session:
            points = session.exec(
                select(Waypoint.easting, Waypoint.northing, Waypoint.elevation_m)
            ).all()
        offsets = []
        inside = 0
        for easting, northing, elevation in points:
            if easting is None or northing is None or not self.dem.contains(easting, northing):
                continue
            inside += 1
            value = self.dem.sample(easting, northing)
            if value is not None and elevation is not None:
                offsets.append(elevation - value)
        if not offsets:
            return {"waypoints": len(points), "inside": inside, "compared": 0}
        arr = np.abs(np.array(offsets))
        return {
            "waypoints": len(points),
            "inside": inside,
            "compared": len(offsets),
            "median_offset_m": round(float(np.median(offsets)), 3),
            "p95_abs_offset_m": round(float(np.percentile(arr, 95)), 3),
        }

    def status(self) -> dict[str, Any]:
        spec = self._spec
        (e0, e1), (n0, n1) = spec.easting_range, spec.northing_range
        lon0, lat0 = en_to_lonlat(e0, n0)
        lon1, lat1 = en_to_lonlat(e1, n1)
        info: dict[str, Any] = {
            "available": self.available,
            "rows": spec.rows,
            "cols": spec.cols,
            "cell_m": spec.cell_m,
            "extent": {"e_min": e0, "e_max": e1, "n_min": n0, "n_max": n1},
            "bounds_deg": {"lon_min": lon0, "lon_max": lon1, "lat_min": lat0, "lat_max": lat1},
        }
        if self.available:
            info["validation"] = self.validation()
            with self._lock:
                overview = self.dem.overview(OVERVIEW_FACTOR * 4)
            info["elevation_m"] = {
                "min": float(np.nanmin(overview)),
                "max": float(np.nanmax(overview)),
            }
        return info

    def drives(self, step_m: float = 0.0) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.exec(
                select(TraverseSegment).order_by(TraverseSegment.source_index)
            ).all()
        out = []
        for index, drive in enumerate(rows):
            points = drive.points
            if step_m > 0 and len(points) > 2:
                kept = [points[0]]
                for p in points[1:-1]:
                    if math.hypot(p[0] - kept[-1][0], p[1] - kept[-1][1]) >= step_m:
                        kept.append(p)
                kept.append(points[-1])
                points = kept
            out.append(
                {
                    "index": index,
                    "sol": drive.sol,
                    "from_rmc": drive.from_rmc,
                    "to_rmc": drive.to_rmc,
                    "length_m": drive.length_m,
                    "points": [[p[0], p[1]] for p in points],
                }
            )
        return out

    # ---- maps ------------------------------------------------------------------------------

    def map_id(self, center_e: float, center_n: float, size_m: int, model: CostModel) -> str:
        payload = json.dumps(
            {
                "c": [round(center_e), round(center_n)],
                "s": size_m,
                "m": model.as_dict(),
                "v": TERRAIN_VERSION,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:20]

    def get_map(
        self, center_e: float, center_n: float, size_m: float, model: CostModel
    ) -> TerrainMap:
        if not MIN_SIZE_M <= size_m <= MAX_SIZE_M:
            raise InvalidRequestError(f"size_m must be within [{MIN_SIZE_M}, {MAX_SIZE_M}]")
        if not self.dem.contains(center_e, center_n):
            raise InvalidRequestError("map centre is outside the DEM coverage")
        cell = max(1, math.ceil(size_m / MAX_GRID_SIDE))
        size = int(math.ceil(size_m / cell) * cell)  # whole planning cells
        key = self.map_id(center_e, center_n, size, model)
        with self._lock:
            cached = self._maps.get(key)
            if cached is not None:
                self._maps.move_to_end(key)
                return cached
            built = self._build(key, center_e, center_n, size, cell, model)
            self._maps[key] = built
            while len(self._maps) > 6:
                self._maps.popitem(last=False)
            return built

    def _build(
        self, key: str, ce: float, cn: float, size: int, cell: int, model: CostModel
    ) -> TerrainMap:
        spec = self._spec
        e_min = float(round(ce - size / 2))
        n_max = float(round(cn + size / 2))
        col0 = round(e_min - (spec.x0 - spec.cell_m / 2))
        row0 = round((spec.y0 + spec.cell_m / 2) - n_max)
        padded = self.dem.window(row0 - PAD_M, col0 - PAD_M, size + 2 * PAD_M, size + 2 * PAD_M)
        layers = traversability(padded, model, cell, pad=PAD_M)
        terrain_map = TerrainMap(
            id=key,
            center_e=ce,
            center_n=cn,
            size_m=size,
            cell_m=cell,
            e_min=e_min,
            n_max=n_max,
            model=model,
            layers=layers,
            clearance=clearance_map(layers, float(cell)),
        )
        self._write_layers(terrain_map, padded)
        return terrain_map

    def _write_layers(self, terrain_map: TerrainMap, padded: np.ndarray) -> None:
        crop = lambda a: a[PAD_M:-PAD_M, PAD_M:-PAD_M]  # noqa: E731
        window = crop(padded)
        directory = self.derived_dir / terrain_map.id
        display = min(DISPLAY_SIDE, terrain_map.size_m)
        resize = lambda a: cv2.resize(a, (display, display), interpolation=cv2.INTER_AREA)  # noqa: E731
        shade = resize(crop(hillshade(padded, 1.0)))
        grey = (np.nan_to_num(shade, nan=0.0) * 215 + 25).astype(np.uint8)
        _write_png(
            directory / "hillshade.png", np.dstack([grey, grey, grey, np.full_like(grey, 255)])
        )
        slope = resize(crop(slope_deg(padded, 1.0)))
        rough = resize(crop(roughness_m(padded, terrain_map.model.roughness_window_m)))
        _write_png(
            directory / "slope.png", _ramp(slope, terrain_map.model.max_slope_deg, SLOPE_RAMP, 200)
        )
        _write_png(
            directory / "roughness.png",
            _ramp(rough, terrain_map.model.max_roughness_m, ROUGH_RAMP, 200),
        )
        risk = terrain_map.layers.risk
        rgba = np.zeros((*risk.shape, 4), np.uint8)
        for index, colour in enumerate(RISK_COLOURS):
            rgba[risk == index] = colour
        _write_png(directory / "risk.png", rgba)

        model = terrain_map.model
        terrain_map.legends = {
            "slope": [
                {"label": f"{v:.0f}°", "color": _hex(c)}
                for v, c in zip(
                    (0, model.max_slope_deg / 2, model.max_slope_deg), SLOPE_RAMP, strict=True
                )
            ],
            "roughness": [
                {"label": f"{v:.2f} m", "color": _hex(c)}
                for v, c in zip(
                    (0, model.max_roughness_m / 2, model.max_roughness_m), ROUGH_RAMP, strict=True
                )
            ],
            "risk": [
                {"label": label, "color": _hex(c)}
                for label, c in zip(RISK_LABELS, RISK_COLOURS, strict=True)
            ],
        }
        finite = terrain_map.layers.slope[np.isfinite(terrain_map.layers.slope)]
        rough_finite = terrain_map.layers.roughness[np.isfinite(terrain_map.layers.roughness)]
        counts = np.bincount(risk.ravel(), minlength=4) / risk.size
        terrain_map.stats = {
            "slope_p50_deg": round(float(np.percentile(finite, 50)), 1) if finite.size else None,
            "slope_p95_deg": round(float(np.percentile(finite, 95)), 1) if finite.size else None,
            "slope_max_deg": round(float(finite.max()), 1) if finite.size else None,
            "roughness_p95_m": round(float(np.percentile(rough_finite, 95)), 3)
            if rough_finite.size
            else None,
            "elevation_min_m": round(float(np.nanmin(window)), 1),
            "elevation_max_m": round(float(np.nanmax(window)), 1),
            "risk_fraction": {
                label: round(float(v), 4) for label, v in zip(RISK_LABELS, counts, strict=True)
            },
        }

    def layer_path(self, map_id: str, layer: str) -> Path:
        if layer not in {"hillshade", "slope", "roughness", "risk"}:
            raise NotFoundError(f"no layer {layer!r}", code="layer_not_found")
        path = self.derived_dir / map_id / f"{layer}.png"
        if not path.is_file():
            raise NotFoundError(f"no map {map_id!r} (build it first)", code="map_not_found")
        return path

    def map_for_drives(
        self, first: int, last: int, margin_m: float, model: CostModel
    ) -> tuple[TerrainMap, list[list[float]]]:
        """A map covering real drives ``first..last`` (indices from :meth:`drives`)."""
        if last < first:
            raise InvalidRequestError("last drive must not precede the first")
        with Session(self._engine) as session:
            rows = session.exec(
                select(TraverseSegment).order_by(TraverseSegment.source_index)
            ).all()
        if not rows:
            raise NoDataError(
                "No drive paths ingested. Run: uv run mars-ingest waypoints",
                code="no_traverse_data",
            )
        if first < 0 or last >= len(rows):
            raise InvalidRequestError(f"drive indices must be within [0, {len(rows) - 1}]")
        points = [p for drive in rows[first : last + 1] for p in drive.points]
        es = [p[0] for p in points]
        ns = [p[1] for p in points]
        size = max(max(es) - min(es), max(ns) - min(ns)) + 2 * margin_m
        if size > MAX_SIZE_M:
            raise InvalidRequestError(
                f"these drives span {size:.0f} m; choose fewer drives (max map {MAX_SIZE_M} m)"
            )
        terrain_map = self.get_map(
            (min(es) + max(es)) / 2, (min(ns) + max(ns)) / 2, max(size, MIN_SIZE_M), model
        )
        return terrain_map, points

    # ---- planning ----------------------------------------------------------------------------

    def plan(
        self,
        terrain_map: TerrainMap,
        start: tuple[float, float],
        goal: tuple[float, float],
        planners: list[str],
        *,
        rrt_seed: int = 42,
        rrt_iterations: int = 3000,
        actual_points: list[list[float]] | None = None,
    ) -> PlanOut:
        unknown = sorted(set(planners) - set(PLANNERS))
        if unknown or not planners:
            raise InvalidRequestError(f"planners must be a non-empty subset of {list(PLANNERS)}")
        grid = PlanningGrid(terrain_map.layers.cost, float(terrain_map.cell_m))
        cells = []
        snapped = False
        for name, (e, n) in (("start", start), ("goal", goal)):
            row, col = terrain_map.to_cell(e, n)
            raw = (round(row), round(col))
            if not grid.inside(*raw):
                raise InvalidRequestError(f"{name} is outside the map")
            cell = grid.nearest_passable(raw, SNAP_RADIUS_CELLS)
            if cell is None:
                raise InvalidRequestError(
                    f"{name} is in impassable terrain (no passable cell nearby)"
                )
            snapped |= cell != raw
            cells.append(cell)
        s, g = cells
        runners = {
            "astar": lambda: astar(grid, s, g),
            "dijkstra": lambda: astar(grid, s, g, heuristic=False),
            "theta_star": lambda: lazy_theta_star(grid, s, g),
            "rrt_star": lambda: rrt_star(grid, s, g, seed=rrt_seed, iterations=rrt_iterations),
        }
        results: dict[str, PlanResult] = {
            name: runners[name]() for name in PLANNERS if name in planners
        }
        metrics: dict[str, RouteMetrics] = {}
        routes = []
        for name, result in results.items():
            m = (
                evaluate(result.path, terrain_map.layers, grid.cell_m, terrain_map.clearance)
                if result.found
                else None
            )
            if m:
                metrics[name] = m
            routes.append(
                RouteOut(
                    planner=name,
                    found=result.found,
                    reason=result.reason,
                    points=[terrain_map.to_en(p) for p in _simplify(result.path)],
                    metrics=m,
                    expanded=result.expanded,
                    elapsed_ms=round(result.elapsed_ms, 1),
                    extra=result.extra,
                )
            )
        actual = None
        if actual_points:
            path = [terrain_map.to_cell(p[0], p[1]) for p in actual_points]
            m = evaluate(path, terrain_map.layers, grid.cell_m, terrain_map.clearance)
            metrics["actual"] = m
            actual = RouteOut(
                "actual", True, None, [(p[0], p[1]) for p in actual_points], m, 0, 0.0, {}
            )
        best, explanation = explain(
            metrics,
            {k: v.expanded for k, v in results.items()},
            terrain_map.model.max_slope_deg,
            rrt_seed if "rrt_star" in results else None,
        )
        if snapped:
            explanation.insert(
                0,
                "Start or goal fell on an impassable cell and was moved to the nearest "
                "passable one.",
            )
        return PlanOut(
            map=terrain_map,
            start=terrain_map.to_en((float(s[0]), float(s[1]))),
            goal=terrain_map.to_en((float(g[0]), float(g[1]))),
            snapped=snapped,
            routes=routes,
            actual=actual,
            best=best,
            explanation=explanation,
        )


__all__ = ["ASSUMPTIONS", "LIMITATIONS", "PLANNERS", "TITLES", "TerrainMap", "TerrainService"]
