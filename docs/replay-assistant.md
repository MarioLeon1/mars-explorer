# Mission Replay and the AI assistant (Phase 5)

## Mission Replay

### What it shows

| Element | Source | Provenance |
|---|---|---|
| Drive distance per sol | JPL MMGIS `M20_traverse.json` (559 drives) | real_observation |
| Images on a sol timeline | each image's own LMST from the raw-images feed | real_observation |
| Drive times on the sol timeline | drive SCLK mapped to LMST (see below) | derived placement of a real drive |
| Frame sequences | stored raw images grouped by command sequence | derived grouping of real frames, labelled **reconstructed** |
| Official videos | NASA Image and Video Library (allowlist of 3) | real_observation, labelled **official NASA video** |

### Sequences: grouping and classification

A sequence is every stored image with the same `(sol, instrument, sequence_id)`. Frames are
ordered by **SCLK** (the spacecraft clock), not by the feed's UTC date, which is wrong around
landing. Classification uses metadata only (`replay/sequences.py`):

| Kind | Rule | What playback means |
|---|---|---|
| `fixed_pointing` | mast camera, one pointing (az/el within 0.5°) | real change over time from one viewpoint |
| `pointing_sweep` | mast camera, several pointings | a pan across mosaic tiles — *not* motion |
| `vehicle_fixed` | Hazcam, EDL, LCAM, SkyCam, CacheCam, helicopter | change over time from the vehicle (which may move); mast az/el does not apply |
| `single_exposure` | all frames share one SCLK | tiles/products of one exposure, not a time series |
| `unclassified` | mast camera without pointing metadata | cannot tell |

Playback offers **real timing** (real gap between exposures ÷ speed, clamped to 40 ms – 3 s,
and the UI says when a long gap was shortened) and a **fixed rate**. Real timing is the default
only for time series. The stage is always stamped `RECONSTRUCTED · not a NASA video`.

Measured on real data (2026-11-17):

| Sequence | Frames | Span | Cadence | Kind |
|---|---|---|---|---|
| sol 0 LCAM `LVS` | 87 | 187 s | ~3.4 s, with a ~1.1 s burst mid-sequence | vehicle_fixed |
| sol 2024 Navcam `NCAM00520` | 21 (1280×256 horizon strip, az 95°, el 0.7°) | 85 s | ~4 s | fixed_pointing |
| sol 2024 Navcam `NCAM00518` | 8 (az −90°, el 30°) | 175 s | ~25 s | fixed_pointing |

> Lesson: an earlier draft described `NCAM00520` with the cadence of `NCAM00518`, because the
> first rows inspected belonged to the other sequence. Descriptions are now written from the
> stored records, and the live test asserts the frame counts.

### SCLK → LMST placement (derived)

MMGIS drives carry SCLK only. They are placed on the sol's LMST axis with
`lmst_h = sclk / 3698.97 s + offset` (one Mars solar day = 88 775.244 s), with the offset taken as
the median over that sol's images that have both LMST and SCLK. The worst residual is reported.
It is 0.9 s on sol 2022 (16 images) and 2.0 s on sol 1000 (13 images), so the mapping is consistent with the
published LMST. Sols with drives but no stored images cannot be placed, and the UI says so.

### Official videos

`replay/videos.py` holds an allowlist of three NASA Image Library videos. For each, the
`~medium.mp4` and poster were checked live (HTTP 200). The library API returns `http://` asset links,
so the code builds the `https://` URL itself and percent-encodes the id (some ids contain `’`).
The browser streams the file directly from NASA (`<video>` needs no CORS) and nothing is stored
locally.

## AI assistant

### Activation

The assistant is disabled until a key exists. `GET /api/assistant/status` returns
`enabled: false` and the steps below, and `POST /api/assistant/chat` answers
`503 assistant_disabled`:

1. Create an API key at <https://platform.claude.com>. API usage is billed separately from a
   Claude.ai subscription.
2. Add `ANTHROPIC_API_KEY=<key>` to `.env` in the repo root. The file is gitignored, and the key
   never reaches the browser.
3. Optionally set `MARS_ASSISTANT_MODEL` (default `claude-opus-5-5`; `claude-haiku-5-5` is
   ~40× cheaper) and `MARS_ASSISTANT_EFFORT` (`low`–`max`, default `medium`).
4. Restart the backend. The startup log line says `AI assistant: enabled (<model>)`.

### Design

- **Manual tool-use loop** with the official `anthropic` Python SDK (`assistant/service.py`),
  capped at 8 tool rounds (configurable).
- **Eight read-only tools** (`assistant/tools.py`): mission overview, rover position, image
  search, image details, drives, sol summary, sequences, terrain status. None of them writes,
  downloads or plans. A test asserts the database file is unchanged after running all eight.
  Bad arguments return `is_error` tool results, never exceptions.
- **Integrity rules in the system prompt:**
  - no invented telemetry;
  - no measurements from single images;
  - detections are candidates;
  - sequences are reconstructed;
  - the assistant cannot plan or drive;
  - cite provenance and app links.
- **Request shape**, per the Claude API docs:
  - thinking is adaptive (always on for Opus 5.5), with depth set by `output_config.effort`;
  - `tool_choice` stays `auto` (forcing a tool returns 400 on current models);
  - the stable system prompt is marked for prompt caching;
  - server-side refusal **fallbacks** (`fallbacks: "default"`, beta
    `server-side-fallback-2026-07-01`) are on, except for Haiku models, which have none;
  - `stop_reason == "refusal"` is reported as a refusal, never shown as an answer.
- **Errors** map to clear codes:
  - `assistant_auth_failed` (401);
  - `assistant_model_not_found` (404);
  - `assistant_rate_limited` (429);
  - `assistant_bad_request` (400);
  - `assistant_unreachable` (network);
  - `assistant_upstream_error` (other 5xx).
- **Responses** carry `label: "ai_generated"`, `provenance: "derived"`, the tool calls made, token
  usage and fallback use. The UI shows an estimated cost per answer.

### Data sent to Anthropic

The question, the visible conversation and the JSON returned by the tools (metadata of public
NASA data, real drives, perception statistics, terrain status). No images or files are sent.

### Tests

`tests/integration/test_assistant_api.py` runs the real SDK against `httpx2.MockTransport` (the
SDK is built on httpx2). It checks the exact request bodies and headers, the tool loop,
refusals, fallbacks, the Haiku path, the round limit and the error mapping. No key and no
network are needed.
