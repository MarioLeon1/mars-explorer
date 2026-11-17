# Perception — engineering notes (Phase 3)

Classical, deterministic computer vision on real Perseverance raw images. Every result is
`derived` data from a named algorithm, with its parameters, timings, score definition and
limitations. Nothing here is a learned model, and nothing is a physical measurement.

## Methods

| Method | Category | What it does | Output |
|---|---|---|---|
| CLAHE | enhancement | local contrast equalisation with a clip limit | image layer |
| Edges and gradients | structure | Canny with median-derived thresholds + Sobel magnitude | 2 layers |
| Rock candidates — scale-space blobs | detection | DoG extrema in (x, y, σ) on the CLAHE image + Hessian edge rejection | candidates |
| Rock candidates — closed edge regions | detection | Canny → morphological closing → contours filtered by area, solidity, aspect, outline sharpness | candidates + edge layer |
| Texture classes (experimental) | segmentation | k-means on per-tile relative texture statistics, ranked smooth → textured | class layer |
| ORB keypoints | features | oriented FAST + rotated BRIEF | keypoint layer |
| Stereo match | features | ORB + Lowe ratio test + RANSAC fundamental matrix on a verified L/R pair | matches, pixel disparity |

Code: `backend/src/mars_explorer/vision/`. The registry (`methods.py`) declares every parameter
with bounds and help text; the UI builds its controls from it.

### Scores are defined, not probabilities

- **Blob contrast** = |DoG| × σ²/(k−1) ÷ std(CLAHE image): how strongly a region stands out at
  its own scale.
- **Outline sharpness** = mean gradient along the region outline ÷ median image gradient.

Neither is calibrated to a probability, so the UI never shows them as "confidence %".

## Findings on real data (2026-11-17)

1. **Rover shadow boundaries** produced many false blob candidates on Hazcam frames. Elongated
   structures have one large and one small principal curvature; the SIFT-style Hessian test
   (trace²/det < (r+1)²/r, r = 10) removes them. A synthetic test (`test_edge_rejection_…`)
   proves the effect with known ground truth.
2. **Large rocks inside the rover's shadow are missed** by both detectors (low local contrast).
   This is reported as a limitation and shows up as low recall in the evaluation.
3. **Texture is confounded by illumination.** With absolute statistics, k-means split sunlit vs.
   shadowed ground instead of textures. Normalising by local brightness fixed that but made dark
   areas look rough (sensor noise ÷ small mean). A noise floor (24 DN) balances both; both knobs
   are exposed in the UI so the trade-off is visible. Marked experimental.
4. **The two detectors largely disagree** (median agreement F1 = 0.37 over 40 Navcam/Hazcam
   images): independent methods point at different places, so neither is "the truth".
5. **Stereo geometry is measurable**: on the sol 2022 Navcam pair, 704 of 905 ratio-test matches
   survive RANSAC; median disparity −153.6 px (IQR 59.7 px, varying with depth) and vertical
   offset 5.0 ± 1 px — the pair is close to rectified. Converting disparity to distance needs the
   CAHVORE camera models and the baseline (later phase).
6. **Performance trap fixed**: permissive parameters produced tens of thousands of raw
   responses and a quadratic non-maximum suppression took minutes. Grid-based NMS with early stop
   at the 300-candidate cap brings the worst case on a real image to ~170 ms (on a P-core).

7. **Benchmark timings depend on which CPU core runs them.** On this i7-14700KF (8 performance
   + 12 efficiency cores) the blob detector measured 157 ms with the process pinned to P-cores and
   342 ms pinned to E-cores; unpinned, after short idle gaps, Windows chose E-cores (~330 ms). I
   first misattributed it to background load — a controlled pinning experiment
   (`SetProcessAffinityMask`) settled it. Benchmarks therefore compare methods within one run.

## Evaluation methodology

There is no labelled ground truth for these images. The user marks rock centres in the UI
(`user_generated` annotations, stored as fractions of width/height). A candidate matches a mark
if their distance ≤ max(candidate radius, 1.5 % of image width); matching is one-to-one, closest
first. Precision/recall assume the user marked every relevant rock in the region, and human
annotation is interpretation — not mission-confirmed truth. The UI states both caveats.

## Benchmark

`uv run mars-vision benchmark` (or the button in the Perception home page) runs both detectors
with default parameters on cached images and writes
[`docs/benchmarks/perception-benchmark.md`](benchmarks/perception-benchmark.md): runtime,
candidates per image, inter-detector agreement and — for annotated images — precision/recall.

## Not done (deliberately)

- No learned model yet. A segmentation network trained on AI4Mars (Curiosity/MER, CC-BY-4.0,
  15 GB) is possible on the RTX 5070, but the domain gap to Perseverance must be measured with
  annotated Perseverance images first — the annotation tool built here is the prerequisite.
- No metric sizes or distances from single images.
