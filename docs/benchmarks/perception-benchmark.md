# Perception benchmark — rock-candidate detectors

Generated 2026-11-17 11:03 UTC by `uv run mars-vision benchmark` (algorithm version 1).

## Dataset

- 40 real Perseverance raw images from the local archive (max 40), cameras: NAVCAM_LEFT, NAVCAM_RIGHT, FRONT_HAZCAM_LEFT_A, FRONT_HAZCAM_RIGHT_A, REAR_HAZCAM_LEFT.
- Rendition: NASA `large` JPEG (≈1200 px wide). Credit: NASA/JPL-Caltech.
- Default parameters for every method (see `vision/methods.py`).

## Results

| Method | Images | Runtime ms (median / p95) | Candidates per image (median) | Annotated images | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Rock candidates — scale-space blobs | 40 | 310.8 / 347.5 | 186 | 0 | - | - | - |
| Rock candidates — closed edge regions | 40 | 31.3 / 48.4 | 138 | 0 | - | - | - |

Agreement between the two detectors (F1, median over images): **0.37**.

## How to read this

- Runtime: this machine, single thread, image decoding excluded (Intel64 Family 6 Model 183 Stepping 1, GenuineIntel, OpenCV 5.0.0).
- Hybrid CPUs (e.g. Intel P-cores + E-cores): Windows may schedule this single-threaded, bursty work on efficiency cores. Measured on an i7-14700KF: blob detector 157 ms pinned to P-cores vs 342 ms pinned to E-cores. Compare methods within one run, not across runs.
- Agreement is not accuracy: it shows how often the two independent methods point at the same places.
- Precision/recall exist only for images annotated by hand in the Perception module, and assume every relevant rock in them was marked. Human annotation is interpretation, not mission-confirmed ground truth.
- Candidates are image regions, not confirmed rocks; sizes are pixels, not metres.
