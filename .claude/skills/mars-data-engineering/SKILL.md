---
name: mars-data-engineering
description: Use when adding or changing ingestion of NASA/JPL data in Mars Explorer (raw-images feed, MMGIS waypoints, PDS products, NASA Image Library), touching backend/src/mars_explorer/ingest/, the db models, or anything about provenance, attribution, dedupe or upstream endpoint behaviour.
---

# Mars data engineering

## Before using any endpoint
1. Check `docs/research/2026-11-16-data-sources-and-toolchain.md` for what was verified live.
2. **Verify it live again** (one small request) before building on it; record the date in code
   comments/docstrings. Old tutorials are often wrong (`api.nasa.gov/mars-photos` is dead).
3. Capture a small **real** response into `backend/tests/fixtures/` and write the parser
   tests against it. Never hand-invent fixture records.

## Rules that already bit us
- Raw-images feed: build queries with httpx `params=` — a literal `|` in the URL → HTTP 400.
- `num` ≤ 100; numbers are strings; `"UNK"` means null; tuples are `"(a,b,c)"` strings;
  `date_taken_utc` has no zone (it is UTC).
- Image files: `Content-Type: image/jpg` (non-standard) and **no CORS** → always serve via backend.
- MMGIS waypoints: `-9999` = missing; mid-drive fixes have `dist_total_m = 0.0` = missing.
- Not every sol has every camera (Hazcams ≈ drive sols). Pick seed sols from real waypoint sols.
- SQLModel requires timezone-aware datetimes.
- Order frames by **SCLK**, not `date_taken_utc` (UTC dates are wrong around landing, sol 0).
- `sequence_id` comes from the product id; one sol/camera often holds several sequences
  (sol 2024 Navcam: `NCAM00518` 8 frames at ~25 s, `NCAM00520` 21 frames at ~4 s). Group before
  describing cadence or pointing.
- NASA Image Library: asset links are `http://` with raw ids (may contain `’`) → build `https://`
  URLs with `urllib.parse.quote`; `<video>` streams without CORS, so official videos are not stored.

## Pipeline contract
- Parse defensively (`ingest/parse.py` helpers): unusable → `None`, never a guessed value.
- Keep the original record verbatim (`raw_json` column + `metadata.json` file).
- Downloads: temp file + `os.replace`, SHA-256, size check, idempotent re-runs, failures
  recorded per item (never abort the whole run).
- Politeness: identified User-Agent, delays from settings, retries with backoff only on
  network errors / 429 / 5xx.
- Every run writes an `ingest_runs` row (`success|partial|failed` + counts + first errors).
- Every API object gets `provenance`; show the record's own `credit`.

## Checklist for a new source
- [ ] live check + fixture captured
- [ ] parser + unit tests on the fixture (missing values, units, time zones)
- [ ] `@pytest.mark.live` smoke test
- [ ] contract doc (`docs/api/`) + TS types updated together
- [ ] attribution text and limitations surfaced in the UI
