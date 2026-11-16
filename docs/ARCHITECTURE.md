# Architecture

## Shape: a modular monolith

One Python service and one web client, each split into modules with explicit interfaces.
For a single-developer, local-first project this gives the separation of microservices without
their operational cost (deployment, networking, distributed failures).

```
frontend (React/TS) ──HTTP /api──▶ backend (FastAPI)
                                    api/        routers + response schemas (contract v1)
                                    ingest/     NASA clients, parser, downloader, CLI
                                    db/         SQLModel tables, engine
                                    core/       config, logging, provenance, errors
                                    (later) vision/ terrain/ navigation/ replay/ assistant/
                                    data/       SQLite + image cache (gitignored)
```

## Key decisions

| Decision | Why | Alternatives considered |
|---|---|---|
| Python backend | OpenCV, rasterio, PyTorch, scientific stack all native | Node backend (weak CV/GIS ecosystem) |
| FastAPI + Pydantic | typed contract, automatic OpenAPI at `/docs`, validation | Flask (untyped), Django (heavier than needed) |
| SQLite (SQLModel) | zero-install, single file, ample for ~10⁵–10⁶ rows | PostgreSQL (server to run; can migrate later) |
| Local image cache + backend proxy | NASA image files send no CORS headers → pixels unusable in canvas/WebGL unless same-origin; caching is also polite | hotlinking NASA URLs directly |
| Contract-first API (`docs/api/contract-v1.md`) | frontend and backend evolve independently; TS types mirror Pydantic schemas | generated clients (more tooling than needed now) |
| React + TS + Vite, no UI kit | full control of a non-generic visual identity; small bundle | MUI/Chakra (generic look), Next.js (SSR not needed) |
| Deterministic planners (Phase 4) | explainable, testable, safe | learning-based control; LLM control (rejected outright) |
| No ROS 2 / Gazebo now | experimental on native Windows, needs WSL2; not needed for a web app | revisit as an optional extension |

## Data flow (Phase 1)

1. `mars-ingest seed` queries the raw-images feed per (sol, camera) with polite delays and retries.
2. Each record is normalised (`ingest/parse.py`): `"UNK"` → null, tuple strings → arrays,
   zone-less UTC → aware UTC, LMST and sequence id extracted. The original JSON is kept verbatim.
3. Renditions are downloaded atomically (temp file + rename), hashed (SHA-256) and indexed;
   re-runs skip what is already cached (idempotent).
4. Waypoints are fetched from JPL MMGIS and replace the table wholesale (the source is authoritative).
5. The API serves metadata from SQLite and files from the cache, fetching missing files on demand.

## Scientific integrity in code

- `Provenance` enum on every API object; the UI renders it as a badge (simulated data is
  hatched + violet + labelled, never colour-only).
- Missing values are `null`, never `0` (e.g. mid-drive odometry `0.0` is treated as missing).
- Notes on each image state its limits (uncalibrated, downsampled on board).

## Known limitations (Phase 1)

- Raw images are not georeferenced; the traverse plot is schematic (local equirectangular).
- MMGIS localizations lag the image feed by days to weeks.
- No database migrations yet (`create_all` at startup); Alembic will be added when the schema
  must evolve with existing user data.
- Vitest must be run with an upper-case drive letter path on Windows (PowerShell does this);
  running it from MSYS bash with `/c/...` loads Vitest twice and every suite fails.
