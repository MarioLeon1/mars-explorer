# Mars Explorer — project guide for Claude

## Purpose
Portfolio-grade Mars rover mission-control app built on **real, traceable NASA Mars 2020 (Perseverance) data**: image exploration, computer vision, terrain/risk analysis, explainable route planning, mission replay, optional AI assistant. Optimise for engineering quality and scientific honesty, not feature count.

The user is the project owner (CS background, new to robotics/planetary science). Reply to them **in Spanish**, explain decisions, and always end with a concrete "Qué hacer ahora".

## Architecture (modular monolith)
- `backend/` — Python 3.13, FastAPI, SQLModel/SQLite, httpx. Package `src/mars_explorer/`:
  - `core/` config (pydantic-settings, `.env`), logging, `Provenance` enum, shared errors
  - `db/` SQLModel tables + session
  - `ingest/` NASA clients (raw-images feed, MMGIS waypoints), downloader, CLI `mars-ingest`
  - `api/` FastAPI app + routers (contract: `docs/api/contract-v1.md`)
  - `vision/` classical CV: method registry (`methods.py`), detectors, texture, ORB matching, evaluation, benchmark CLI `mars-vision`
  - `terrain/` PLACES 1 m DEM reader (memmap), derived layers, map service, CLI `mars-terrain`
  - `navigation/` grid planners (A*, Dijkstra, Lazy Theta*, k-nearest RRT*), metrics, explanations
  - later: `replay/`, `assistant/`
- `frontend/` — Vite + React 19 + TypeScript. `src/design-system/` (tokens, primitives), `src/modules/<module>/`, `src/api/` (typed client mirroring the contract). Vite proxies `/api` → `127.0.0.1:8000`.
- `data/` — local only (gitignored): `mars.db`, `images/`, later `terrain/`.
- `docs/` — `SETUP.md` (step-by-step guide), `ARCHITECTURE.md`, `api/`, `research/`.

## Commands
```powershell
# backend (run inside backend/)
uv sync                                   # install deps from uv.lock
uv run pytest                             # unit+integration tests (offline)
uv run pytest -m live                     # opt-in tests against real NASA endpoints
uv run ruff check . ; uv run ruff format .
uv run mars-ingest seed                   # download curated real image set + waypoints
uv run mars-vision benchmark              # perception benchmark -> docs/benchmarks/
uv run mars-terrain fetch                 # download the 1 m orbital DEM (~325 MB, resumable)
uv run mars-terrain status                # DEM validation against real localizations
uv run uvicorn mars_explorer.api.app:app --reload --port 8000
# frontend (run inside frontend/)
npm install ; npm run dev ; npm test ; npm run build ; npm run lint
# both at once (repo root)
.\scripts\dev.ps1
```

## Scientific-integrity rules (non-negotiable)
1. Every data object carries `provenance`: `real_observation` | `derived` | `simulated` | `user_generated`. The UI shows it as a badge.
2. Never present simulated telemetry, positions, battery, sensor readings or movement as real. There is **no public real-time power/battery telemetry** — do not display any.
3. Preserve the original NASA record (raw JSON) and show each item's own `credit`. Footer: "Not affiliated with or endorsed by NASA/JPL". No NASA logos.
4. Raw images are uncalibrated browse products — never derive physical measurements (slope, size, distance) from a single 2D image.
5. Detections must state their method (algorithmic / model prediction / human interpretation / confirmed). Show confidence only when technically meaningful.
6. LLMs never control navigation. Planning is deterministic and explainable.
7. Frame sequences rebuilt from raw images are labelled "reconstructed", never "NASA video".

## Data-source facts (verified 2026-11-16, see docs/research/)
- Raw images: `https://mars.nasa.gov/rss/api/?feed=raw_images&category=mars2020&feedtype=json` — always pass query **params via httpx `params=`** (a literal `|` in the URL returns HTTP 400). `num` max 100; numeric `extended` fields are strings, may be `"UNK"`; tuples are strings `"(a,b,c)"`.
- `api.nasa.gov/mars-photos` is **dead** (404). Do not use.
- Image files have no CORS headers → serve through backend (`/api/images/{id}/file/{size}`).
- Real rover positions: MMGIS `M20_waypoints.json` (lon/lat/elev_geoid, `-9999` = missing).
- Torch (later): only from `https://download.pytorch.org/whl/cu132` (RTX 5070 = sm_120); plain pip gives CPU build.

## Conventions
- Python: type hints everywhere, Pydantic models at boundaries, `logging` (no prints in library code), ruff clean. Tests in `backend/tests/{unit,integration}`, network-free by default (use `httpx.MockTransport` + fixtures in `tests/fixtures/`, which are real captured responses).
- TypeScript: strict, no `any`, functional components, CSS custom properties from `design-system/tokens.css`, no UI framework. Tests with Vitest + Testing Library next to code (`*.test.ts(x)`).
- No secrets in code; config via `.env` (see `.env.example`). No large data in git.
- Don't delete or weaken tests to make them pass. Don't claim a feature works without running it.

## Gotchas
- Run Vitest from PowerShell (`C:\...`). From MSYS/Git Bash (`/c/...`) Vitest loads twice → every suite fails.
- Headless Edge screenshots: `Start-Process -Wait` + a separate `--user-data-dir` (see `.claude/skills/mars-ui-design`).
- Mid-drive MMGIS fixes report `dist_total_m = 0.0` → treated as missing.
- Feed `id=<unknown>` returns HTTP 200 with the generic latest list (not an error) → `fetch_by_id` matches `image[].imageid`.
- Stereo partner id = swap eye letter (`NLG_`↔`NRG_`, `ZL0_`↔`ZR0_`); not always published → verify before calling it a pair.
- Not every sol has every camera (sol 1200: 0 Navcam, 84 others). Check `/api/feed/availability` first.
- Background ingest: one worker thread (`ingest/jobs.py`); job state in memory, durable record in `ingest_runs`.
- CV: see `.claude/skills/computer-vision` + `docs/perception.md`. Bump `vision.ALGORITHM_VERSION` when an algorithm changes (analysis cache key).
- Windows console is cp1252: CLI output must stay ASCII (files are UTF-8).
- `.visually-hidden` must keep `top/left: 0` or hidden text stretches the document.
- Terrain/navigation: see `.claude/skills/autonomous-navigation` + `docs/terrain-navigation.md`.

## Status
- Phase 0 (env, repo, skeleton) — done 2026-11-16.
- Phase 1 (ingest seed, API contract v1, Mission Control UI) — done 2026-11-16.
  Backend 47 tests + 3 live; frontend 28 tests; `scripts/check.ps1` green.
- Phase 2 (Explorer, contract v1.1, background ingest jobs) — done 2026-11-16.
  Backend 62 tests + 3 live; frontend 47 tests.
- Phase 3 (Perception, contract v1.2, annotations + evaluation, benchmark) — done 2026-11-17.
  Backend 88 tests + 3 live; frontend 55 tests.
- Phase 4 (Terrain & Navigation, contract v1.3, real drive replanning) — done 2026-11-17.
  Backend 125 tests + 3 live; frontend 63 tests.
- Next: Phase 5 Mission Replay + optional AI assistant.
