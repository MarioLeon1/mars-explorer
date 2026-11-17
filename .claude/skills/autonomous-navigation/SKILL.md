---
name: autonomous-navigation
description: Use when changing Mars Explorer terrain processing or route planning (backend/src/mars_explorer/terrain/, navigation/, the Terrain & Navigation UI in frontend/src/modules/terrain/), adding planners, changing the cost model, or reporting planning results.
---

# Terrain & autonomous navigation

Read `docs/terrain-navigation.md` first (data, georeferencing, calibration, findings).

## Invariants
- Planning is deterministic and explainable. Randomised planners must be seeded and report the seed.
  No language model may choose or alter routes; explanations are template-based from metrics.
- Every route, including the rover's real drive, is scored by `navigation/metrics.evaluate` on the
  same layers — never compare planner-internal costs directly.
- The cost model is an assumption: keep limits user-adjustable, state them in `layers.ASSUMPTIONS`,
  and re-check the calibration (0 of 708 real localizations impassable) when defaults change.
- Real drive comparisons use the dense MMGIS traverse, never straight lines between localizations.
- Bump `terrain.TERRAIN_VERSION` when a derived-layer algorithm changes (map cache key).

## Verified facts / traps
- DEM pixel centre (r, c): e = 4340890.5 + c, n = 1097069.5 − r; same grid as MMGIS easting/northing.
- Read maps with `PAD_M` of real terrain; filters at borders otherwise invent roughness.
- Grid ≤ 300 cells/side keeps Python planners interactive. Profile before optimising
  (`segment_cost` is the hot path for Theta*/RRT*).
- Diagonal moves must not cut between two impassable cells.

## Adding a planner
1. Function in `navigation/planners.py` returning `PlanResult` (path in grid (row, col)).
2. Register in `terrain/service.PLANNERS` + runners, `metrics.TITLES`, frontend `ROUTE_STYLE`
   (next categorical slot; validate the palette with the dataviz validator).
3. Unit tests on synthetic grids with known optimal costs, walls, gaps and unreachable goals;
   an API test on the synthetic DEM (`tests/terrain_scenes.py`).
