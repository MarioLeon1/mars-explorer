"""Image-space path sketch on synthetic scenes with known rock positions."""

from __future__ import annotations

import math

import numpy as np
import pytest

from mars_explorer.vision.pathsketch import SketchParams, estimate_horizon, sketch_path
from tests.vision_scenes import ROCKS, SIZE, rock_scene

HEIGHT, WIDTH = SIZE


def frac(x: float, y: float) -> tuple[float, float]:
    return x / WIDTH, y / HEIGHT


@pytest.fixture(scope="module")
def scene() -> np.ndarray:
    return rock_scene(with_shadow_edge=False)


def test_path_bends_around_a_rock_on_the_straight_line(scene: np.ndarray) -> None:
    x, y, r = ROCKS[1]  # (330, 220, 20)
    sketch = sketch_path(
        scene, goal=frac(x, y - 4 * r), start=frac(x, y + 5 * r), params=SketchParams(horizon=0.0)
    )
    assert sketch.found, sketch.reason
    assert sketch.blocking_straight >= 1
    assert sketch.length_px > sketch.straight_px  # it had to detour
    assert sketch.min_clearance_px is not None and sketch.min_clearance_px > 0
    # Every vertex keeps clear of the true rock disc.
    for px, py in sketch.path:
        assert math.hypot(px - x, py - y) > r
    assert any("crosses" in line for line in sketch.explanation)
    assert any("pixels" in line for line in sketch.explanation)


def test_detected_obstacles_match_the_true_rocks(scene: np.ndarray) -> None:
    sketch = sketch_path(scene, goal=(0.5, 0.1), params=SketchParams(horizon=0.0))
    for x, y, r in ROCKS:
        assert any(math.hypot(o.x - x, o.y - y) < r for o in sketch.obstacles), (x, y)


def test_is_deterministic(scene: np.ndarray) -> None:
    params = SketchParams(horizon=0.0, clearance=2.0)
    a = sketch_path(scene, goal=(0.8, 0.15), params=params)
    b = sketch_path(scene, goal=(0.8, 0.15), params=params)
    assert a.path == b.path and a.cost_png == b.cost_png


def test_horizon_is_estimated_from_a_smooth_sky(scene: np.ndarray) -> None:
    sky = scene.copy()
    sky[:150] = 230  # featureless bright sky over the top 31 %
    assert estimate_horizon(sky) == pytest.approx(150 / HEIGHT, abs=0.05)
    assert estimate_horizon(scene) == 0.0  # textured to the top: no sky
    sketch = sketch_path(sky, goal=(0.5, 0.5))
    assert sketch.horizon_auto and sketch.horizon == pytest.approx(150 / HEIGHT, abs=0.05)
    assert all(py >= sketch.horizon * HEIGHT for _, py in sketch.path)


def test_goal_in_the_sky_is_refused(scene: np.ndarray) -> None:
    sketch = sketch_path(scene, goal=(0.5, 0.02), params=SketchParams(horizon=0.6))
    assert not sketch.found
    assert sketch.reason is not None and "goal" in sketch.reason
    assert sketch.path == []


def test_contour_detector_also_works(scene: np.ndarray) -> None:
    sketch = sketch_path(
        scene, goal=(0.5, 0.1), params=SketchParams(detector="contours", horizon=0)
    )
    assert sketch.found and sketch.obstacles
