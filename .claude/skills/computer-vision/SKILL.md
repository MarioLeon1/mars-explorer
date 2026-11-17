---
name: computer-vision
description: Use when adding or changing perception methods in Mars Explorer (backend/src/mars_explorer/vision/, the Perception UI in frontend/src/modules/perception/), tuning detectors, adding learned models, or reporting CV results/benchmarks.
---

# Computer vision in Mars Explorer

Read `docs/perception.md` first (methods, real-data findings, evaluation methodology).

## Adding a method
1. Pure function in `vision/<topic>.py` (NumPy in, dataclasses out; no I/O).
2. Register a `MethodSpec` in `vision/methods.py`: every parameter as a `ParamSpec` with bounds,
   step and help text; `limitations` (mandatory); `score_definition` if it scores anything;
   `experimental=True` until validated. The UI form is generated from this.
3. Bump `vision.ALGORITHM_VERSION` when any existing algorithm changes (invalidates cached analyses).
4. Tests with **synthetic scenes of known ground truth** (`tests/vision_scenes.py`) for behaviour,
   plus an API test; never hand-tune to pass on one real image.
5. Look at results on several REAL images (Navcam terrain, Hazcam with rover shadow, Mastcam-Z)
   before declaring defaults — render overlays and inspect them.

## Integrity rules for CV
- Results are `derived`; method kind `algorithmic` (or `model_prediction` once models exist).
- Scores are defined in words and never shown as probabilities/"confidence %".
- No metric size/distance from a single raw image; pixel units only. Disparity → depth needs
  CAHVORE models + baseline.
- Precision/recall only against user annotations, always with the caveats.

## Known traps (verified)
- Rover shadow boundaries → false blobs (keep the Hessian edge test).
- Absolute texture follows illumination; relative texture amplifies shadow noise (noise floor).
- Permissive params explode candidate counts → keep grid NMS with early stop and the cap.
- Large frames: detectors work at ≤1024 px and map back; parameters are in input pixels.
- Real stereo pairs: right − left disparity is NEGATIVE.

## Learned models (future)
Torch only from the cu132 index (RTX 5070, sm_120). AI4Mars (CC-BY-4.0) has a domain gap to
Perseverance: measure it against Perseverance annotations made in the Perception UI before trusting it.
