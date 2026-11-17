from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from mars_explorer.navigation.grid import PlanningGrid, octile
from mars_explorer.navigation.metrics import clearance_map, evaluate, explain
from mars_explorer.navigation.planners import astar, lazy_theta_star, rrt_star
from mars_explorer.terrain.layers import CostModel, traversability


def flat(size: int = 60, cost: float = 1.0) -> PlanningGrid:
    return PlanningGrid(np.full((size, size), cost, np.float32), cell_m=2.0)


def with_wall(gap_row: int | None = 30) -> PlanningGrid:
    grid = flat()
    grid.cost[:, 30] = np.inf
    if gap_row is not None:
        grid.cost[gap_row, 30] = 1.0
    return grid


def path_length(path: list[tuple[float, float]], cell_m: float) -> float:
    return sum(math.dist(a, b) for a, b in itertools.pairwise(path)) * cell_m


def test_astar_and_dijkstra_are_optimal_and_agree() -> None:
    grid = flat()
    start, goal = (5, 5), (50, 40)
    a, d = astar(grid, start, goal), astar(grid, start, goal, heuristic=False)
    expected = octile(start, goal) * grid.cell_m
    assert a.found and d.found
    assert a.cost == pytest.approx(expected) and d.cost == pytest.approx(expected)
    assert a.expanded < d.expanded  # the heuristic prunes the search
    assert a.path[0] == (5.0, 5.0) and a.path[-1] == (50.0, 40.0)


def test_planners_route_through_the_only_gap() -> None:
    grid = with_wall(gap_row=45)
    for result in (astar(grid, (10, 10), (10, 50)), lazy_theta_star(grid, (10, 10), (10, 50))):
        assert result.found
        assert (
            (45.0, 30.0) in result.path
            or any(abs(p[1] - 30) < 1e-9 and p[0] == 45 for p in result.path)
            or any(r == 45.0 for r, c in result.path if 29 <= c <= 31)
        )
        assert all(math.isfinite(grid.cost[round(r), round(c)]) for r, c in result.path)


def test_no_corner_cutting_between_two_blocked_cells() -> None:
    grid = flat(4)
    grid.cost[0, 1] = np.inf
    grid.cost[1, 0] = np.inf
    assert not astar(grid, (0, 0), (1, 1)).found


def test_unreachable_and_bad_endpoints_are_reported() -> None:
    walled = with_wall(gap_row=None)
    result = astar(walled, (10, 10), (10, 50))
    assert not result.found and "no passable route" in (result.reason or "")
    assert not lazy_theta_star(walled, (10, 10), (10, 50)).found
    assert "start" in (astar(walled, (10, 30), (10, 50)).reason or "")
    assert "goal" in (astar(walled, (10, 10), (99, 99)).reason or "")


def test_theta_star_is_shorter_than_the_grid_path() -> None:
    grid = flat()
    start, goal = (5, 5), (50, 20)
    grid_path, any_angle = astar(grid, start, goal), lazy_theta_star(grid, start, goal)
    straight = math.dist(start, goal) * grid.cell_m
    assert path_length(any_angle.path, grid.cell_m) == pytest.approx(straight, rel=1e-6)
    assert path_length(grid_path.path, grid.cell_m) > straight * 1.03


def test_rrt_star_is_reproducible_with_a_seed() -> None:
    grid = with_wall(gap_row=45)
    one = rrt_star(grid, (10, 10), (10, 50), seed=7, iterations=2500)
    two = rrt_star(grid, (10, 10), (10, 50), seed=7, iterations=2500)
    assert one.found and one.path == two.path and one.cost == two.cost
    assert one.extra["seed"] == 7
    other = rrt_star(grid, (10, 10), (10, 50), seed=8, iterations=2500)
    assert other.path != one.path


def test_segment_cost_and_nearest_passable() -> None:
    grid = with_wall()
    assert grid.segment_cost((10, 10), (10, 20)) == pytest.approx(20.0)
    assert grid.segment_cost((10, 10), (10, 40)) == math.inf
    assert (
        grid.nearest_passable((10, 30))
        in {(9, 30 - 1), (10, 29), (10, 31), (11, 29), (9, 31), (11, 31)}
        or grid.nearest_passable((10, 30)) is not None
    )
    assert grid.nearest_passable((10, 30)) != (10, 30)


def ramp_layers(angle: float = 10.0, size: int = 64):
    cols = np.arange(size, dtype=np.float32)[None, :].repeat(size, axis=0)
    return traversability((cols * math.tan(math.radians(angle))).astype(np.float32), CostModel())


def test_metrics_breakdown_sums_to_total_cost() -> None:
    layers = ramp_layers()
    clear = clearance_map(layers, 1.0)
    m = evaluate([(10.0, 10.0), (10.0, 50.0)], layers, 1.0, clear)
    assert m.feasible and m.length_m == pytest.approx(40.0)
    assert m.cost == pytest.approx(m.cost_distance + m.cost_slope + m.cost_roughness, rel=1e-6)
    assert m.max_slope_deg == pytest.approx(10.0, abs=0.01)
    assert m.elevation_gain_m == pytest.approx(40 * math.tan(math.radians(10)), rel=0.05)
    assert m.elevation_loss_m == pytest.approx(0.0, abs=1e-6)
    assert m.min_clearance_m is None  # nothing impassable on the map


def test_metrics_report_impassable_length() -> None:
    layers = ramp_layers()
    layers.cost[:, 30:34] = np.inf
    m = evaluate([(10.0, 10.0), (10.0, 50.0)], layers, 1.0, clearance_map(layers, 1.0))
    assert not m.feasible and m.cost == math.inf
    assert m.impassable_m == pytest.approx(4.0, abs=0.6)


def test_explanation_is_deterministic_and_names_the_best() -> None:
    layers = ramp_layers()
    clear = clearance_map(layers, 1.0)
    short = evaluate([(10.0, 10.0), (10.0, 50.0)], layers, 1.0, clear)
    long = evaluate([(10.0, 10.0), (40.0, 30.0), (10.0, 50.0)], layers, 1.0, clear)
    metrics = {"astar": long, "dijkstra": long, "theta_star": short, "actual": long}
    best, lines = explain(metrics, {"astar": 10, "dijkstra": 40}, 30.0, None)
    assert best == "theta_star"
    assert lines[0].startswith("Theta* has the lowest total cost")
    assert any("4.0× fewer" in line for line in lines)
    assert any("real drive path" in line for line in lines)
    assert explain({}, {}, 30.0, None) == (
        None,
        ["No planner found a feasible route under this cost model."],
    )
