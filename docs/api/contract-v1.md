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
