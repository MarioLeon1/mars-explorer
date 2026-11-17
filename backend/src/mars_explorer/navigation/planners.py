"""Grid planners: Dijkstra, A*, Lazy Theta* (any-angle) and RRT* (sampling-based).

All operate on the same :class:`PlanningGrid` and cost model so their results are comparable:

* **Dijkstra** — uniform-cost search; optimal on the 8-connected grid; no heuristic.
* **A\\*** — Dijkstra + admissible heuristic (octile distance × minimum cost per metre = 1);
  returns an optimal path of the same cost while expanding fewer nodes.
* **Lazy Theta\\*** — A* variant whose paths may connect any two cells in line of sight, removing
  the 45°-staircase artefacts of grid paths. Not guaranteed optimal.
* **RRT\\*** — random tree in continuous space with rewiring; asymptotically optimal, randomised
  (seeded for reproducibility). Included as the classic sampling-based baseline.
"""

from __future__ import annotations

import heapq
import math
import random
import time
from dataclasses import dataclass, field

import numpy as np

from mars_explorer.navigation.grid import NEIGHBOURS, Cell, PlanningGrid, Point, octile


@dataclass(slots=True)
class PlanResult:
    planner: str
    found: bool
    path: list[Point] = field(default_factory=list)  # (row, col) waypoints
    cost: float = math.inf
    expanded: int = 0
    elapsed_ms: float = 0.0
    reason: str | None = None
    extra: dict[str, float | int] = field(default_factory=dict)


def _reconstruct(parents: dict[Cell, Cell], goal: Cell) -> list[Point]:
    path = [goal]
    while path[-1] in parents:
        path.append(parents[path[-1]])
    path.reverse()
    return [(float(r), float(c)) for r, c in path]


def _check_endpoints(grid: PlanningGrid, start: Cell, goal: Cell, name: str) -> PlanResult | None:
    if not grid.passable(start):
        return PlanResult(name, False, reason="start cell is impassable or outside the map")
    if not grid.passable(goal):
        return PlanResult(name, False, reason="goal cell is impassable or outside the map")
    return None


def astar(grid: PlanningGrid, start: Cell, goal: Cell, *, heuristic: bool = True) -> PlanResult:
    """A* (heuristic=True) or Dijkstra (heuristic=False) on the 8-connected grid.

    Edge cost = step length × mean of the two cells' cost per metre. The heuristic is
    octile distance × cell size × 1.0 (the minimum possible cost per metre), so it never
    overestimates: A* stays optimal."""
    name = "astar" if heuristic else "dijkstra"
    failed = _check_endpoints(grid, start, goal, name)
    if failed:
        return failed
    started = time.perf_counter()
    cost, cell_m = grid.cost, grid.cell_m
    rows, cols = grid.shape
    g: dict[Cell, float] = {start: 0.0}
    parents: dict[Cell, Cell] = {}
    closed: set[Cell] = set()
    h = (lambda cell: octile(cell, goal) * cell_m) if heuristic else (lambda cell: 0.0)
    frontier: list[tuple[float, float, Cell]] = [(h(start), 0.0, start)]
    expanded = 0
    while frontier:
        _, g_here, here = heapq.heappop(frontier)
        if here in closed:
            continue
        closed.add(here)
        expanded += 1
        if here == goal:
            return PlanResult(
                name,
                True,
                _reconstruct(parents, goal),
                g_here,
                expanded,
                (time.perf_counter() - started) * 1000,
            )
        r, c = here
        c_here = float(cost[r, c])
        for dr, dc, step in NEIGHBOURS:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols) or (nr, nc) in closed:
                continue
            c_next = float(cost[nr, nc])
            if not math.isfinite(c_next):
                continue
            # Diagonal moves may not cut between two impassable cells.
            if dr and dc and not (math.isfinite(cost[r, nc]) and math.isfinite(cost[nr, c])):
                continue
            candidate = g_here + step * cell_m * (c_here + c_next) / 2
            if candidate < g.get((nr, nc), math.inf):
                g[(nr, nc)] = candidate
                parents[(nr, nc)] = here
                heapq.heappush(frontier, (candidate + h((nr, nc)), candidate, (nr, nc)))
    return PlanResult(
        name,
        False,
        expanded=expanded,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        reason="no passable route between start and goal under this cost model",
    )


def lazy_theta_star(grid: PlanningGrid, start: Cell, goal: Cell) -> PlanResult:
    """Lazy Theta*: assume line of sight to the grandparent and verify only on expansion."""
    name = "theta_star"
    failed = _check_endpoints(grid, start, goal, name)
    if failed:
        return failed
    started = time.perf_counter()
    cost, cell_m = grid.cost, grid.cell_m
    rows, cols = grid.shape
    g: dict[Cell, float] = {start: 0.0}
    parent: dict[Cell, Cell] = {start: start}
    closed: set[Cell] = set()

    def h(cell: Cell) -> float:
        return math.hypot(cell[0] - goal[0], cell[1] - goal[1]) * cell_m  # euclidean, admissible

    def seg(a: Cell, b: Cell) -> float:
        return grid.segment_cost((float(a[0]), float(a[1])), (float(b[0]), float(b[1])))

    frontier: list[tuple[float, Cell]] = [(h(start), start)]
    expanded = 0
    while frontier:
        _, here = heapq.heappop(frontier)
        if here in closed:
            continue
        # Lazy check: the cost stored for `here` was an estimate. Now compute real segment costs
        # and keep the cheapest of: the assumed parent (any-angle) or a closed neighbour.
        p = parent[here]
        if p != here:
            best = (g[p] + seg(p, here), p)
            r, c = here
            for dr, dc, _ in NEIGHBOURS:
                nb = (r + dr, c + dc)
                if nb in closed and nb != p:
                    option = g[nb] + seg(nb, here)
                    if option < best[0]:
                        best = (option, nb)
            if not math.isfinite(best[0]):
                continue  # unreachable after all; drop it
            g[here], parent[here] = best
        closed.add(here)
        expanded += 1
        if here == goal:
            path = [goal]
            while parent[path[-1]] != path[-1]:
                path.append(parent[path[-1]])
            path.reverse()
            return PlanResult(
                name,
                True,
                [(float(r), float(c)) for r, c in path],
                g[goal],
                expanded,
                (time.perf_counter() - started) * 1000,
            )
        r, c = here
        p = parent[here]
        for dr, dc, step in NEIGHBOURS:
            nb = (r + dr, c + dc)
            nr, nc = nb
            if not (0 <= nr < rows and 0 <= nc < cols) or nb in closed:
                continue
            if not math.isfinite(cost[nr, nc]):
                continue
            # Path 2 (lazy): connect to the parent directly, estimated with the grid step cost.
            estimate = g[p] + math.hypot(nr - p[0], nc - p[1]) * cell_m * (
                (float(cost[p]) + float(cost[nr, nc])) / 2
            )
            local = g[here] + step * cell_m * (float(cost[r, c]) + float(cost[nr, nc])) / 2
            candidate, via = (estimate, p) if estimate < local else (local, here)
            if candidate < g.get(nb, math.inf):
                g[nb] = candidate
                parent[nb] = via
                heapq.heappush(frontier, (candidate + h(nb), nb))
    return PlanResult(
        name,
        False,
        expanded=expanded,
        elapsed_ms=(time.perf_counter() - started) * 1000,
        reason="no passable route between start and goal under this cost model",
    )


def rrt_star(
    grid: PlanningGrid,
    start: Cell,
    goal: Cell,
    *,
    seed: int = 42,
    iterations: int = 3000,
    step_cells: float = 10.0,
    goal_bias: float = 0.08,
) -> PlanResult:
    """k-nearest RRT* in continuous (row, col) space. Seeded: reproducible.

    Each iteration samples a point (goal-biased), steers at most ``step_cells`` from the nearest
    tree node, connects through the cheapest of the k ≈ 2e·ln(n) nearest nodes, then rewires those
    neighbours through the new node when cheaper. Node coordinates live in a NumPy array so the
    neighbour searches are vectorised."""
    name = "rrt_star"
    failed = _check_endpoints(grid, start, goal, name)
    if failed:
        return failed
    started = time.perf_counter()
    rng = random.Random(seed)
    rows, cols = grid.shape
    coords = np.empty((iterations + 1, 2), dtype=np.float64)
    coords[0] = start
    count = 1
    parents: list[int] = [-1]
    g: list[float] = [0.0]
    goal_point = (float(goal[0]), float(goal[1]))
    best_goal: tuple[float, int] = (math.inf, -1)

    for _ in range(iterations):
        if rng.random() < goal_bias:
            target = goal_point
        else:
            target = (rng.uniform(0, rows - 1), rng.uniform(0, cols - 1))
        d2 = ((coords[:count] - target) ** 2).sum(axis=1)
        i_near = int(d2.argmin())
        base = (float(coords[i_near, 0]), float(coords[i_near, 1]))
        distance = math.sqrt(float(d2[i_near]))
        if distance == 0:
            continue
        scale = min(1.0, step_cells / distance)
        new = (base[0] + (target[0] - base[0]) * scale, base[1] + (target[1] - base[1]) * scale)
        if not math.isfinite(grid.cost[round(new[0]), round(new[1])]):
            continue

        radius = max(
            step_cells * 1.5, 3 * step_cells * math.sqrt(math.log(count + 1) / (count + 1))
        )
        d2_new = ((coords[:count] - new) ** 2).sum(axis=1)
        inside = np.flatnonzero(d2_new <= radius * radius)
        k = math.ceil(2 * math.e * math.log(count + 1))
        if inside.size > k:
            inside = inside[np.argpartition(d2_new[inside], k - 1)[:k]]
        candidates = [int(i) for i in inside] or [i_near]

        best = (math.inf, -1)
        for i in candidates:
            option = g[i] + grid.segment_cost((coords[i, 0], coords[i, 1]), new)
            if option < best[0]:
                best = (option, i)
        if not math.isfinite(best[0]):
            continue
        index = count
        coords[index] = new
        count += 1
        parents.append(best[1])
        g.append(best[0])
        for i in candidates:  # rewire neighbours through the new node if cheaper
            if i == best[1]:
                continue
            option = best[0] + grid.segment_cost(new, (coords[i, 0], coords[i, 1]))
            if option < g[i]:
                parents[i] = index
                g[i] = option
        if math.hypot(new[0] - goal_point[0], new[1] - goal_point[1]) <= step_cells:
            total = best[0] + grid.segment_cost(new, goal_point)
            if total < best_goal[0]:
                best_goal = (total, index)

    elapsed = (time.perf_counter() - started) * 1000
    extra: dict[str, float | int] = {"seed": seed, "iterations": iterations, "tree_nodes": count}
    if best_goal[1] < 0:
        return PlanResult(
            name,
            False,
            expanded=count,
            elapsed_ms=elapsed,
            extra=extra,
            reason=f"goal not reached within {iterations} iterations (seed {seed})",
        )
    path = [goal_point]
    i = best_goal[1]
    while i >= 0:
        path.append((float(coords[i, 0]), float(coords[i, 1])))
        i = parents[i]
    path.reverse()
    return PlanResult(name, True, path, best_goal[0], count, elapsed, extra=extra)
