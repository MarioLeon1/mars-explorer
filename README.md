# Mars Explorer

A mission-control style application for exploring **real NASA Mars 2020 Perseverance data**:
raw rover imagery, real rover localizations and (in later phases) computer vision, terrain
cost maps and explainable autonomous route planning.

> Imagery & data: NASA/JPL-Caltech and partners. Not affiliated with or endorsed by NASA/JPL.

## Principles

- **Real and traceable.** Every record keeps its original NASA metadata and credit; every
  object carries a provenance label: `real_observation`, `derived`, `simulated` or `user_generated`.
- **Honest limits.** Raw images are uncalibrated browse products; nothing is measured from a
  single 2D photo; no fake telemetry (NASA publishes no real-time power/thermal data).
- **Deterministic autonomy.** Route planning (Phase 4) uses explainable algorithms on a defined
  cost map. A language model never controls the rover.

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Environment, repository, architecture | done |
| 1 | Ingestion pipeline, REST API, Mission Control UI | **done** |
| 2 | Explorer: filters, viewer, comparison, chronology | next |
| 3 | Perception: OpenCV pipeline, obstacle candidates, segmentation | planned |
| 4 | Terrain (real 1 m DEM) + route planning (A*, Dijkstra, Theta*, RRT*) | planned |
| 5 | Mission replay + optional AI assistant | planned |
| 6 | Portfolio polish, E2E tests, case study | planned |

## Architecture

```
Browser ── Vite dev server (React + TS, :5173) ──/api──▶ FastAPI (:8000)
                                                          ├─ ingest/   NASA raw-images feed, JPL MMGIS waypoints
                                                          ├─ api/      contract v1 (docs/api/contract-v1.md)
                                                          └─ db/       SQLite + local image cache (data/)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for decisions and trade-offs.

## Quick start (Windows, PowerShell)

Prerequisites: Git, [uv](https://docs.astral.sh/uv/), Node.js 26 LTS. Full beginner guide:
[docs/SETUP.md](docs/SETUP.md) (in Spanish).

```powershell
.\scripts\setup.ps1 -Seed   # install dependencies + download ~13 MB of real data
.\scripts\dev.ps1           # start API + UI and open http://localhost:5173
.\scripts\check.ps1         # lint, type-check, tests and build
```

Ingest more data:

```powershell
cd backend
uv run mars-ingest images --sol 1200 --camera NAVCAM_LEFT --camera MCZ_LEFT --limit 30
uv run mars-ingest waypoints
uv run mars-ingest status
```

API documentation (OpenAPI) is served at http://127.0.0.1:8000/docs while the backend runs.

## Data sources (verified 2026-11-16)

| Source | Used for | Notes |
|---|---|---|
| NASA Mars 2020 raw-images JSON feed (`mars.nasa.gov/rss/api`) | images + metadata | undocumented; parsed defensively; ≤100 per page |
| JPL MMGIS `M20_waypoints.json` | real rover localizations | `-9999` and mid-drive `0.0` odometry treated as missing |
| `api.nasa.gov/mars-photos` | — | **discontinued (HTTP 404)**; not used |

Details: [docs/research/2026-11-16-data-sources-and-toolchain.md](docs/research/2026-11-16-data-sources-and-toolchain.md).

## Tech stack

Python 3.13 · FastAPI · SQLModel/SQLite · httpx · pytest · ruff — TypeScript · React 19 · Vite ·
Vitest · Testing Library · oxlint. No UI framework; custom design system in `frontend/src/design-system`.
