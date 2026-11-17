# API contract v1 (Phase 1)

Base path: `/api`. JSON, `snake_case`. Datetimes ISO-8601 **with `Z`** (UTC). The raw feed's `date_taken_utc` has no zone; it is UTC — append `Z`.
Errors: HTTP status + `{"error": {"code": "<snake_code>", "message": "<human text>"}}`.

Shared enums:
- `Provenance`: `"real_observation" | "derived" | "simulated" | "user_generated"`
- `CameraGroup`: `"navcam" | "hazcam_front" | "hazcam_rear" | "mastcamz" | "skycam" | "supercam" | "sherloc" | "pixl" | "cachecam" | "edl" | "helicopter" | "other"`
- `ImageSize`: `"small" | "large" | "full_res"` (small = NASA `_320.jpg`, large = `_1200.jpg`, full_res = `.png`)

Shared objects:
```jsonc
// SourceRef
{ "name": "NASA Mars 2020 raw images feed", "url": "https://...", "credit": "NASA/JPL-Caltech" | null, "retrieved_at": "2026-11-16T17:45:00Z" | null }

// Camera
{ "instrument": "NAVCAM_LEFT", "group": "navcam", "label": "Navigation Camera — left (Navcam)" }
```

## GET /api/health
`{ "status": "ok", "version": "0.1.0" }`

## GET /api/mission
Static, sourced mission facts (provenance `real_observation`):
```jsonc
{
  "mission": "Mars 2020", "rover": "Perseverance",
  "launch_date": "2020-07-30", "landing_date": "2021-02-18",
  "landing_site": { "name": "Octavia E. Butler Landing", "region": "Jezero crater", "lat": 18.4447, "lon": 77.4508 },
  "summary": "<1–2 sentence factual summary>",
  "provenance": "real_observation",
  "sources": [SourceRef]
}
```

## GET /api/cameras
Known camera catalog with counts of ingested images (count may be 0):
`[ { ...Camera, "image_count": 12 } ]` ordered by group then instrument.

## GET /api/sols
`[ { "sol": 2024, "image_count": 14, "instruments": ["MCZ_LEFT","NAVCAM_LEFT"], "earliest_utc": "...Z", "latest_utc": "...Z" } ]` ordered by sol desc.

## GET /api/images
Query: `sol` (int), `sol_min`, `sol_max`, `camera` (instrument, repeatable), `group` (CameraGroup, repeatable), `limit` (1–200, default 50), `offset` (default 0), `order` (`desc`|`asc` by sol then date_taken, default `desc`).
```jsonc
{ "items": [ImageSummary], "total": 128, "limit": 50, "offset": 0 }
```
`ImageSummary`:
```jsonc
{
  "image_id": "NLG_2024_0846620381_164ECM_N0930000NCAM00518_00_2I3J",
  "sol": 2024,
  "camera": Camera,
  "sample_type": "Full",
  "date_taken_utc": "2026-10-30T08:44:57.868Z",
  "date_taken_mars": "Sol-02024M12:35:01.653",
  "lmst": "12:35:01",                 // parsed from date_taken_mars, null if unparsable
  "site": 93, "drive": 0,             // drive parsed to int, null if not numeric
  "width": 1280, "height": 960,       // from extended.dimension, null if unknown
  "thumb_url": "/api/images/<id>/file/small",
  "preview_url": "/api/images/<id>/file/large",
  "credit": "NASA/JPL-Caltech",
  "provenance": "real_observation"
}
```

## GET /api/images/{image_id}
`ImageDetail` = `ImageSummary` plus:
```jsonc
{
  "title": "...", "caption": "...",
  "date_received": "2026-10-30T11:56:00Z" | null,
  "filter_name": "UNK" | "ZCAM_L0_RGB" | null,
  "sequence_id": "NCAM00518" | null,       // parsed from image_id segment 5 chars [8:]
  "mast_az": -90.4883 | null, "mast_el": 29.6688 | null,   // degrees
  "sclk": 846620382.316 | null,
  "scale_factor": 4.0 | null,
  "subframe_rect": [1, 1, 5120, 3840] | null,
  "attitude_quaternion": [0.682313, 0.00347943, 0.0627555, 0.728354] | null,
  "camera_model_type": "CAHVORE" | null,
  "camera_position": [x, y, z] | null,
  "camera_vector": [x, y, z] | null,
  "source": {
    "nasa_page_url": "https://mars.nasa.gov/mars2020/multimedia/raw-images/<id>",
    "nasa_json_url": "https://mars.nasa.gov/rss/api/?...&id=<id>",
    "original_files": { "small": "...", "medium": "...", "large": "...", "full_res": "..." }
  },
  "local_files": { "small": true, "large": true, "full_res": false },
  "ingested_at": "...Z",
  "notes": ["Uncalibrated browse product (raw JPEG/PNG). Not suitable for radiometric or photogrammetric measurement."]
}
```
404 `image_not_found`.

## GET /api/images/{image_id}/file/{size}
Serves the cached local file (correct `Content-Type`, `Cache-Control: public, max-age=86400`). If not cached locally, downloads it from NASA once (polite, with retries), stores it, then serves it. 404 `image_not_found` if unknown id; 502 `upstream_unavailable` if NASA download fails.

## GET /api/rover/position
Latest **real** end-of-drive localization from JPL MMGIS (ingested), provenance `real_observation`:
```jsonc
{
  "sol": 2022, "site": 93, "drive": 0,
  "lat": 18.43559434, "lon": 77.23322287,
  "elevation_m": -1936.37,               // elev_geoid (m, relative to Mars areoid)
  "roll_deg": 5.58, "pitch_deg": 4.69, "yaw_deg": 93.97, "tilt_deg": 7.29,
  "drive_distance_m": 22.061, "odometry_total_m": 45245.71,
  "note": "End-of-drive localization",
  // NOTE: waypoint `images[]` panorama URLs (Layers/mosaics/*.jpg) return HTTP 403 (checked 2026-11-16) — not exposed.
  "provenance": "real_observation",
  "source": SourceRef,
  "caveats": ["Localizations are published with a delay; the latest images may be newer than this position."]
}
```
503 `no_position_data` if waypoints were never ingested.

## GET /api/rover/waypoints
All ingested localizations (for the traverse plot), sorted by sol, site, drive:
`{ "items": [ { "sol": 13, "site": 3, "drive": 0, "lat": .., "lon": .., "elevation_m": .. | null, "odometry_total_m": .. } ], "provenance": "real_observation", "source": SourceRef }`

## GET /api/system/status
```jsonc
{
  "api": "ok",
  "database": { "images": 128, "sols": 8, "waypoints": 708 },
  "storage": { "image_files": 256, "bytes": 31457280 },
  "last_ingest": { "kind": "seed" | "images" | "waypoints", "status": "success" | "partial" | "failed", "finished_at": "...Z", "items_added": 120, "items_skipped": 8, "items_failed": 0 } | null,
  "feed": { "latest_sol": 2031, "total_images": 1055868, "checked_at": "...Z" } | null
}
```
`feed` comes from the last `latest=true` check stored during ingestion (never fetched synchronously by this endpoint).

---

# v1.1 additions (Phase 2: Explorer) — backwards compatible

## GET /api/images — extra filters
`date_from`, `date_to` (YYYY-MM-DD, UTC date taken, inclusive), `q` (case-insensitive substring of
`image_id`, LIKE wildcards escaped). All filters are shared with `/neighbors`.

## GET /api/images/{image_id}/neighbors
Same filter params as `/api/images`. Chronological order = (sol, date_taken_utc, image_id) ascending.
```jsonc
{ "previous": ImageSummary | null, "next": ImageSummary | null,
  "position": 12 | null,   // 1-based; null if the image is outside the filter
  "total": 111 }
```

## GET /api/images/{image_id}/related
```jsonc
{
  "same_sequence": [ImageSummary],            // same sol + sequence_id, chronological, ≤30
  "stereo": {                                  // null for non-stereo cameras
    "partner_instrument": "NAVCAM_RIGHT",
    "candidate_id": "NRG_…",                   // id the other eye WOULD have — unverified
    "local": ImageSummary | null               // present only if actually stored
  } | null,
  "same_sol_other_cameras": [ImageSummary]     // closest in time first, ≤8
}
```

## GET /api/images/{image_id}/raw
`{ "image_id", "provenance", "source_url", "record": { …original NASA record verbatim… } }`

## POST /api/images/{image_id}/stereo-partner
Fetches the candidate partner from NASA **only if published** and ingests it (small + large).
200 `ImageSummary` · 404 `stereo_partner_not_found` · 422 `not_stereo` · 502 `upstream_unavailable`.
Note: for an unknown id the NASA feed silently returns the generic latest list (HTTP 200); the
backend detects this and never stores a wrong image.

## GET /api/feed/availability?sol_min=&sol_max=&camera=…
Live count from NASA (cached 10 min) vs. local count.
`{ "sol_min", "sol_max", "cameras": [...], "published": 66 | null, "stored": 15, "checked_at", "source": SourceRef }`

## Ingestion jobs (one background worker, ≤3 queued/running, in-memory progress)
`POST /api/ingest/jobs` body `{ "sol_min": 1201, "sol_max": 1203?, "cameras": ["NAVCAM_LEFT"], "limit": 50, "full_res": false }`
→ 202 `IngestJob`. Limits: ≤31 sols per job, `limit` 1–200, known instruments only (422 `invalid_request`);
429 `too_many_jobs`.
`GET /api/ingest/jobs` (newest first) · `GET /api/ingest/jobs/{id}` (404 `job_not_found`).
```jsonc
// IngestJob
{ "id": "a1b2c3d4e5f6", "status": "queued|running|success|partial|failed|cancelled",
  "sol_min": 1201, "sol_max": 1201, "cameras": ["NAVCAM_LEFT"], "limit": 50, "full_res": false,
  "progress": { "seen": 12, "added": 10, "skipped": 2, "failed": 0, "downloaded": 20 },
  "run_id": 7 | null, "error": null, "created_at": "…Z", "started_at": "…Z" | null, "finished_at": "…Z" | null }
```

---

# v1.2 additions (Phase 3: Perception) — backwards compatible

All analysis outputs have `provenance: "derived"` and `method_kind: "algorithmic"`; annotations
are `"user_generated"`. Coordinates of detections are pixels of the analysed rendition
(`width` × `height`); annotations are fractions (0–1) of width/height.

| Method | Path | Notes |
|---|---|---|
| GET | `/api/vision/methods` | catalogue: params (type, default, min/max/step, choices, help), limitations, `score_definition`, `experimental`, `produces_detections` |
| POST | `/api/vision/analyses` | body `{image_id, method, params?, rendition?: "large"\|"full_res"}` → `VisionAnalysis`; cached by hash(image, method, rendition, params, algorithm version); 422 `invalid_request` for unknown method/params or out-of-range values |
| GET | `/api/vision/analyses/{id}` | stored analysis (404 `analysis_not_found`) |
| GET | `/api/vision/analyses/{id}/layers/{name}.png` | RGBA overlay, same size as the analysed rendition |
| GET | `/api/vision/analyses/{id}/evaluation` | precision/recall/F1 vs. the image's annotations (422 if the method has no detections) |
| GET/POST | `/api/images/{id}/annotations` | list / add `{x, y, label: "rock"}` (201) |
| DELETE | `/api/annotations/{id}` | 204; 404 `annotation_not_found` |
| POST | `/api/vision/match` | `{image_a, image_b}` → keypoints, ratio-test matches, RANSAC inliers, pixel disparity stats, ≤300 drawn matches, `stereo_pair` flag |
| POST | `/api/vision/benchmark` | `{cameras?, limit ≤ 80}` → per-detector runtime/candidates summaries, agreement F1, precision/recall on annotated images |

```jsonc
// VisionAnalysis
{ "id": "6ed3c597…", "image_id": "…", "method": "rocks_blob", "title": "…", "method_kind": "algorithmic",
  "provenance": "derived", "rendition": "large", "params": { …resolved… }, "algorithm_version": "1",
  "width": 1200, "height": 896, "timings_ms": { "dog_scale_space": 149.5 },
  "stats": { "candidates": 9, "score_median": 1.1, "capped": "yes - strongest 300 kept"? },
  "detections": [ { "x": 412.3, "y": 288.0, "r": 11.2, "score": 1.42, "area_px": 394.1 } ] | null,
  "layers": [ { "name": "edges", "label": "…", "url": "/api/vision/analyses/…/layers/edges.png" } ],
  "score_definition": "…" | null, "limitations": ["…"], "created_at": "…Z" }
```

---

# v1.3 additions (Phase 4: Terrain & Navigation) — backwards compatible

Coordinates are easting/northing (metres) in the PLACES DEM projection (`{e, n}`).

| Method | Path | Notes |
|---|---|---|
| GET | `/api/terrain/status` | DEM availability, size, extent, lon/lat bounds, elevation range, validation vs. real localizations, source; `how_to_get` if missing |
| GET | `/api/terrain/overview.png` | whole-DEM shaded relief at 10 m/px |
| GET | `/api/terrain/drives?step_m=10` | real drive paths (index, sol, RMCs, length, thinned points) |
| POST | `/api/terrain/maps` | `{center:{e,n}, size_m 100–3000, cost_model?}` or `{drives:[first,last], margin_m?, cost_model?}` → `TerrainMap` (layers hillshade/slope/roughness/risk with legends, stats, drives in view, assumptions, limitations); 503 `terrain_not_available` |
| GET | `/api/terrain/maps/{id}/layers/{name}.png` | layer PNG |
| POST | `/api/navigation/plans` | `{map: MapRequest, start?, goal?, planners[], rrt_seed, rrt_iterations}` → routes (+ `actual` when planning over drives), metrics, profiles, `best`, `explanation` |

`cost_model`: `{max_slope_deg 5–45 (30), slope_weight 0–20 (4), max_roughness_m 0.05–2 (0.30), roughness_weight 0–20 (3)}`.
Route `kind`: `deterministic` (A*, Dijkstra, Theta*), `randomized` (RRT*, with `extra.seed`), `real_observation` (the rover's drive).
Metrics: `length_m, impassable_m, cost (null if blocked), cost_distance/slope/roughness, max/mean_slope_deg, max_roughness_m, elevation_gain/loss_m, min_clearance_m, profile [[distance, elevation]]`.

---

# v1.4 additions (Phase 5: Mission Replay + AI assistant) — backwards compatible

| Method | Path | Notes |
|---|---|---|
| GET | `/api/replay/mission` | every sol with stored images or a real drive: `{sol, images, sequences, drives, drive_m}` + totals, sources |
| GET | `/api/replay/sols/{sol}` | sol timeline: images with LMST, sequences (≥2 frames), real drives with derived LMST placement, end-of-sol localization, `lmst_calibration`, previous/next sol; 404 if nothing stored |
| GET | `/api/replay/sequences?sol=&min_frames=3` | reconstructed sequences (`label: "reconstructed"`, `provenance: "derived"`) |
| GET | `/api/replay/sequences/{id}` | frames in SCLK order with `t_offset_s`, notes, credits, `real_time_available`; id = `<sol>-<instrument>-<sequence_id or NOSEQ>` |
| GET | `/api/replay/featured` | curated published sequences with `local_frames`, `sequence_url` (once stored) and a ready `job_request` for `POST /api/ingest/jobs` |
| GET | `/api/replay/videos` | official NASA Image Library videos (`label: "official_nasa_video"`), https asset + poster + page URLs, credit |
| GET | `/api/assistant/status` | `enabled`, model, effort, fallbacks, tools, `how_to_enable`, `data_sent`, `never`, pricing |
| POST | `/api/assistant/chat` | `{messages: [{role, content}] (1–40, last = user), context?: {page, sol, image_id}}` → `{reply, model, stop_reason, refused, fallback_used, rounds, tool_calls, usage, notes, label: "ai_generated", provenance: "derived"}`; `503 assistant_disabled` without a key; 502/429 `assistant_*` upstream errors |

Sequence `kind`: `fixed_pointing | pointing_sweep | vehicle_fixed | single_exposure | unclassified`.
