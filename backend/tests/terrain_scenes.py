"""Synthetic DEMs with known geometry, written in the exact PLACES binary layout.

Placed (by easting/northing) so that the real drive paths in
``fixtures/mmgis_traverse_sample.json`` fall inside them.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from mars_explorer.terrain.dem import DemSpec, lonlat_to_en

FIXTURE = Path(__file__).parent / "fixtures" / "mmgis_traverse_sample.json"


def fixture_bounds() -> tuple[float, float, float, float]:
    features = json.loads(FIXTURE.read_text(encoding="utf-8"))["features"]
    points = [lonlat_to_en(c[0], c[1]) for f in features for c in f["geometry"]["coordinates"]]
    es = [p[0] for p in points]
    ns = [p[1] for p in points]
    return min(es), max(es), min(ns), max(ns)


def synthetic_spec(margin: int = 400) -> DemSpec:
    e0, e1, n0, n1 = fixture_bounds()
    cols = math.ceil(e1 - e0) + 2 * margin
    rows = math.ceil(n1 - n0) + 2 * margin
    return DemSpec(
        rows=rows,
        cols=cols,
        offset=128,
        x0=math.floor(e0) - margin + 0.5,
        y0=math.ceil(n1) + margin - 0.5,
    )


def synthetic_elevation(spec: DemSpec) -> np.ndarray:
    """Gentle tilted plain with a steep circular mesa (impassable rim) east of centre."""
    rows, cols = np.mgrid[0 : spec.rows, 0 : spec.cols].astype(np.float32)
    z = -2400.0 + 0.02 * cols - 0.01 * rows  # ≈1.3° regional slope
    cy, cx = spec.rows * 0.5, spec.cols * 0.8
    r = np.hypot(rows - cy, cols - cx)
    z += np.clip((60 - r) * 2.0, 0, 40)  # 63° walls up to a 40 m high plateau
    return z.astype(np.float32)


def write_dem(path: Path, spec: DemSpec, elevation: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(b"\0" * spec.offset)
        handle.write(elevation.astype(">f4").tobytes())
    assert path.stat().st_size == spec.nbytes
