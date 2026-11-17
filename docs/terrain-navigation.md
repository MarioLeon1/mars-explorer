# Terrain & navigation — engineering notes (Phase 4)

Route planning on **real Martian terrain**: the Mars 2020 PLACES orbital DEM (1 m/pixel, PDS),
compared with **the rover's real drive paths** (JPL MMGIS traverse, ~1 m vertices).

## Data

| Product | Source | Use | Provenance |
|---|---|---|---|
| `m20_orbital_dem.img` (14 800 × 5 480, float32 BE, 324.5 MB) | PDS Geosciences, PLACES bundle | elevation | real_observation (mission product) |
| `M20_waypoints.json` (708 localizations) | JPL MMGIS | validation, latest position | real_observation |
| `M20_traverse.json` (559 drives, 36 661 vertices) | JPL MMGIS | real drive paths, replanning endpoints | real_observation |
| slope, roughness, risk, cost, routes | computed here | planning | derived |

**Georeferencing** (from the embedded ODL header): equirectangular, sphere R = 3396.19 km,
standard parallel 18.4663°, pixel centre (r, c) at easting 4340890.5 + c, northing 1097069.5 − r.

**Validation** (`uv run mars-terrain status`): our lon/lat → easting/northing reproduces JPL's
values within 1 mm, and all 708 real localizations fall inside the DEM with a **median elevation
offset of 0.002 m (95 % within 0.114 m)** between JPL's waypoint elevations and the DEM.

## Cost model (explicit assumptions)

`cost per metre = 1 + w_s·(slope/max_slope)² + w_r·(roughness/max_roughness)²`; cells beyond
either limit, or without data, are impassable. Slope by central differences on 1 m posts;
roughness = std of residuals from the local 5 m mean. Planning cells aggregate 1 m posts
conservatively (max slope/roughness). Maps are read with an 8 m margin of real terrain so the
neighbourhood filters never see an artificial border (a test caught a 0.19 m fake roughness at
map edges before this).

**Calibration:** with limits 30° / 0.30 m, none of the 708 real localizations falls on an
impassable cell (max observed in a 5 m neighbourhood: 28.8°, 0.23 m); with 25° four would. These
are engineering assumptions validated against where the rover actually drove — not JPL's
operational limits, which are not public.

## Planners

| Planner | Guarantees | Notes |
|---|---|---|
| Dijkstra | optimal on the 8-connected grid | baseline, no heuristic |
| A* | optimal (admissible octile heuristic × min cost 1) | same cost as Dijkstra, far fewer expansions |
| Lazy Theta* | any-angle, not guaranteed optimal | removes 45° staircases; segments verified on expansion |
| RRT* (k-nearest) | asymptotically optimal, randomised | seeded and reported; reproducible |

All routes (and the real drive) are re-sampled every half cell and scored with the **same**
metrics: length, cost split into distance / slope / roughness, max & mean slope, elevation gain
and loss, clearance to the nearest impassable cell, and the length crossing impassable cells.
The "why this route" text is generated from those metrics by fixed templates — no language
model is involved anywhere in planning or explaining.

## Findings on real data (2026-11-17)

- Replanning the last six real drives (sols 1965 → 2022, 169 m driven): plans of ~107 m with a
  max slope of 11.5°; A* expanded 8.2× fewer nodes than Dijkstra for the same optimum; Theta*
  1 % shorter; RRT* (seed 42) +2 % cost. The rover's path went over a small crest (17.3°) — it
  served science and operations goals this orbital model does not see.
- Sols 1000 → 1018 (7 drives, 724 m reconstructed vs. 710 m odometry): the real path never
  crosses a cell the model calls impassable (closest approach 10.8 m).
- Joining sparse localizations with straight lines is misleading (a straight segment crossed a
  34.6° cell the rover never drove on); using the dense MMGIS traverse fixed the comparison.

## Performance notes

- Grid side capped at 300 cells (cell = map size / 300, min 1 m) to keep pure-Python search
  interactive: A* ~40 ms, Dijkstra ~100 ms, Theta* ~0.6 s, RRT* ~1 s on real maps.
- RRT* was O(n²) on small maps (all nodes inside the rewiring radius): switched to k-nearest
  rewiring with vectorised neighbour search, and removed `np.linspace` from the segment-cost hot
  path after profiling (27.7 s → 2.6 s on the test scenario).

## Limitations

- 1 m posts cannot see rocks or steps smaller than about a metre — the hazards the real rover
  detects with its own stereo cameras (AutoNav). Orbital DEM errors of decimetres propagate.
- No wheel–soil interaction, sand traps, power, communications, time or science objectives.
- Planning is 2D on a cost raster; vehicle footprint and heading are not modelled.
