"""Registry of perception methods: declared parameters, honest descriptions, and runners.

The UI builds its controls from these specs, so every parameter shown to the user is
documented, bounded and validated in one place.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from mars_explorer.core.errors import InvalidRequestError
from mars_explorer.vision import ops
from mars_explorer.vision.features import detect_keypoints
from mars_explorer.vision.rocks import Candidate, detect_blobs, detect_contours
from mars_explorer.vision.texture import NOISE_FLOOR, texture_classes

RGBA = NDArray[np.uint8]
ParamValue = int | float | bool | str

# Colours in RGB (design tokens): signal cyan, Mars-oxide accent ramp.
SIGNAL = (92, 200, 214)
ACCENT = (217, 102, 58)
TEXTURE_RAMP = [(74, 52, 42), (150, 84, 52), (217, 102, 58), (240, 160, 122), (250, 215, 190)]


@dataclass(frozen=True, slots=True)
class ParamSpec:
    name: str
    label: str
    type: Literal["int", "float", "bool", "choice"]
    default: ParamValue
    help: str
    min: float | None = None
    max: float | None = None
    step: float | None = None
    choices: tuple[str, ...] = ()

    def coerce(self, value: Any) -> ParamValue:
        try:
            if self.type == "bool":
                if isinstance(value, bool):
                    return value
                raise TypeError
            if self.type == "choice":
                if value not in self.choices:
                    raise ValueError
                return str(value)
            number = float(value)
            if isinstance(value, bool) or not np.isfinite(number):
                raise TypeError
        except (TypeError, ValueError):
            raise InvalidRequestError(f"invalid value for {self.name}: {value!r}") from None
        if self.type == "int":
            if not number.is_integer():
                raise InvalidRequestError(f"{self.name} must be an integer")
            number = int(number)
        if (self.min is not None and number < self.min) or (
            self.max is not None and number > self.max
        ):
            raise InvalidRequestError(f"{self.name} must be within [{self.min}, {self.max}]")
        return number


@dataclass(slots=True)
class Layer:
    name: str
    label: str
    rgba: RGBA


@dataclass(slots=True)
class MethodOutput:
    layers: list[Layer] = field(default_factory=list)
    detections: list[Candidate] | None = None
    stats: dict[str, float | int | str] = field(default_factory=dict)
    timings_ms: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def timed(self, step: str) -> Iterator[None]:
        start = time.perf_counter()
        yield
        self.timings_ms[step] = round((time.perf_counter() - start) * 1000, 2)


Runner = Callable[[ops.Gray, dict[str, ParamValue], MethodOutput], None]


@dataclass(frozen=True, slots=True)
class MethodSpec:
    name: str
    title: str
    category: Literal["enhancement", "structure", "detection", "segmentation", "features"]
    kind: Literal["algorithmic"]
    summary: str
    params: tuple[ParamSpec, ...]
    limitations: tuple[str, ...]
    run: Runner
    score_definition: str | None = None
    experimental: bool = False

    def resolve(self, given: dict[str, Any] | None) -> dict[str, ParamValue]:
        given = dict(given or {})
        unknown = set(given) - {p.name for p in self.params}
        if unknown:
            raise InvalidRequestError(f"unknown parameter(s) for {self.name}: {sorted(unknown)}")
        return {
            p.name: p.coerce(given[p.name]) if p.name in given else p.default for p in self.params
        }


# ---- layer helpers ----------------------------------------------------------------------


def gray_layer(gray: ops.Gray) -> RGBA:
    rgba = np.empty((*gray.shape, 4), np.uint8)
    rgba[..., :3] = gray[..., None]
    rgba[..., 3] = 255
    return rgba


def mask_layer(mask: NDArray[np.bool_], colour: tuple[int, int, int], alpha: int = 255) -> RGBA:
    rgba = np.zeros((*mask.shape, 4), np.uint8)
    rgba[mask, :3] = colour
    rgba[mask, 3] = alpha
    return rgba


def intensity_layer(values: ops.Gray, colour: tuple[int, int, int]) -> RGBA:
    rgba = np.zeros((*values.shape, 4), np.uint8)
    rgba[..., :3] = colour
    rgba[..., 3] = values
    return rgba


# ---- runners ----------------------------------------------------------------------------


def _run_clahe(gray: ops.Gray, p: dict[str, ParamValue], out: MethodOutput) -> None:
    with out.timed("clahe"):
        enhanced = ops.clahe(gray, float(p["clip_limit"]), int(p["tiles"]))
    out.layers.append(Layer("enhanced", "Contrast-enhanced (CLAHE)", gray_layer(enhanced)))
    out.stats.update(
        input_std=round(float(gray.std()), 2), output_std=round(float(enhanced.std()), 2)
    )


def _run_edges(gray: ops.Gray, p: dict[str, ParamValue], out: MethodOutput) -> None:
    with out.timed("canny"):
        edges = ops.canny_auto(gray, float(p["sigma"]), float(p["blur"]))
    with out.timed("sobel"):
        magnitude = ops.to_uint8(ops.gradient_magnitude(gray, float(p["blur"])))
    out.layers.append(Layer("edges", "Canny edges", mask_layer(edges > 0, SIGNAL)))
    out.layers.append(
        Layer("gradient", "Gradient magnitude (Sobel)", intensity_layer(magnitude, ACCENT))
    )
    out.stats.update(edge_pixel_fraction=round(float((edges > 0).mean()), 4))


MAX_CANDIDATES = 300
"""Detectors keep at most this many candidates (strongest first)."""


def _detection_stats(found: list[Candidate], out: MethodOutput) -> None:
    out.stats["candidates"] = len(found)
    if len(found) >= MAX_CANDIDATES:
        out.stats["capped"] = f"yes - strongest {MAX_CANDIDATES} kept"
    if found:
        scores = [c.score for c in found]
        radii = [c.r for c in found]
        out.stats.update(
            score_median=round(float(np.median(scores)), 3),
            radius_px_median=round(float(np.median(radii)), 1),
        )


def _run_blobs(gray: ops.Gray, p: dict[str, ParamValue], out: MethodOutput) -> None:
    if float(p["max_radius"]) <= float(p["min_radius"]):
        raise InvalidRequestError("max_radius must be greater than min_radius")
    with out.timed("dog_scale_space"):
        found = detect_blobs(
            gray,
            max_candidates=MAX_CANDIDATES,
            min_radius=float(p["min_radius"]),
            max_radius=float(p["max_radius"]),
            min_strength=float(p["min_strength"]),
            edge_ratio=float(p["edge_ratio"]),
            polarity=str(p["polarity"]),
            roi_top=float(p["roi_top"]),
        )
    out.detections = found
    _detection_stats(found, out)


def _run_contours(gray: ops.Gray, p: dict[str, ParamValue], out: MethodOutput) -> None:
    if float(p["max_area"]) <= float(p["min_area"]):
        raise InvalidRequestError("max_area must be greater than min_area")
    with out.timed("contours"):
        found = detect_contours(
            gray,
            max_candidates=MAX_CANDIDATES,
            min_area=float(p["min_area"]),
            max_area=float(p["max_area"]),
            min_solidity=float(p["min_solidity"]),
            min_edge_strength=float(p["min_edge_strength"]),
            roi_top=float(p["roi_top"]),
        )
    with out.timed("edges_layer"):
        edges = ops.canny_auto(ops.clahe(gray))
    out.layers.append(
        Layer("edges", "Edges used (Canny on CLAHE)", mask_layer(edges > 0, SIGNAL, 150))
    )
    out.detections = found
    _detection_stats(found, out)


def _run_texture(gray: ops.Gray, p: dict[str, ParamValue], out: MethodOutput) -> None:
    k = int(p["k"])
    with out.timed("kmeans"):
        result = texture_classes(
            gray,
            tile=int(p["tile"]),
            k=k,
            relative=bool(p["relative"]),
            noise_floor=float(p["noise_floor"]),
        )
    labels = result.labels
    # Sequential single-hue ramp (dark → light = smooth → textured), sampled evenly for k.
    ramp = [TEXTURE_RAMP[round(i * (len(TEXTURE_RAMP) - 1) / (k - 1))] for i in range(k)]
    rgba_tiles = np.zeros((*labels.shape, 4), np.uint8)
    for cls in range(k):
        rgba_tiles[labels == cls, :3] = ramp[cls]
        rgba_tiles[labels == cls, 3] = 120
    full = np.zeros((*gray.shape, 4), np.uint8)
    up = cv2.resize(
        rgba_tiles,
        (labels.shape[1] * result.tile, labels.shape[0] * result.tile),
        interpolation=cv2.INTER_NEAREST,
    )
    full[: up.shape[0], : up.shape[1]] = up
    out.layers.append(Layer("texture", "Texture classes (smooth → textured)", full))
    for cls, share in enumerate(result.fractions):
        out.stats[f"class_{cls + 1}_share"] = round(share, 3)


def _run_keypoints(gray: ops.Gray, p: dict[str, ParamValue], out: MethodOutput) -> None:
    with out.timed("orb"):
        keypoints = detect_keypoints(gray, n_features=int(p["n_features"]))
    canvas = np.zeros((*gray.shape, 4), np.uint8)
    for kp in keypoints:
        cv2.circle(
            canvas,
            (round(kp.x), round(kp.y)),
            max(2, round(kp.size / 6)),
            (*SIGNAL, 230),
            1,
            cv2.LINE_AA,
        )
    out.layers.append(Layer("keypoints", "ORB keypoints", canvas))
    grid = np.zeros((8, 8), bool)
    for kp in keypoints:
        grid[min(7, int(kp.y / gray.shape[0] * 8)), min(7, int(kp.x / gray.shape[1] * 8))] = True
    out.stats.update(keypoints=len(keypoints), grid_coverage=round(float(grid.mean()), 3))


_ROI = ParamSpec(
    "roi_top",
    "Ignore top band",
    "float",
    0.0,
    "Fraction of the image height (from the top) excluded, e.g. sky or distant terrain.",
    0.0,
    0.8,
    0.05,
)

METHODS: dict[str, MethodSpec] = {
    spec.name: spec
    for spec in (
        MethodSpec(
            name="clahe",
            title="Contrast enhancement (CLAHE)",
            category="enhancement",
            kind="algorithmic",
            summary="Equalises contrast locally, tile by tile, with a clip limit that caps noise "
            "amplification. Makes structure in shadows and bright sand visible.",
            params=(
                ParamSpec(
                    "clip_limit",
                    "Clip limit",
                    "float",
                    2.0,
                    "Higher = stronger local contrast (and more noise).",
                    1.0,
                    8.0,
                    0.5,
                ),
                ParamSpec(
                    "tiles", "Tiles per side", "int", 8, "Grid used for local histograms.", 2, 16, 1
                ),
            ),
            limitations=(
                "Display aid only: it changes pixel values non-linearly, so it must not "
                "be used for radiometric comparison.",
            ),
            run=_run_clahe,
        ),
        MethodSpec(
            name="edges",
            title="Edges and gradients",
            category="structure",
            kind="algorithmic",
            summary="Canny edges with thresholds derived from the image median, plus Sobel "
            "gradient magnitude.",
            params=(
                ParamSpec(
                    "sigma",
                    "Threshold spread",
                    "float",
                    0.33,
                    "Canny thresholds = median × (1 ± sigma).",
                    0.05,
                    0.9,
                    0.01,
                ),
                ParamSpec(
                    "blur",
                    "Pre-blur σ (px)",
                    "float",
                    1.2,
                    "Gaussian smoothing before differentiation.",
                    0.0,
                    4.0,
                    0.1,
                ),
            ),
            limitations=(
                "Edges mark intensity changes: rock outlines, but also shadows, ripples "
                "and rover hardware.",
            ),
            run=_run_edges,
        ),
        MethodSpec(
            name="rocks_blob",
            title="Rock candidates — scale-space blobs",
            category="detection",
            kind="algorithmic",
            summary="Difference-of-Gaussians extrema across scales on the CLAHE image; elongated "
            "responses (shadow edges, ridges) are rejected with a Hessian curvature test "
            "as in SIFT.",
            params=(
                ParamSpec(
                    "min_radius",
                    "Min radius (px)",
                    "float",
                    6.0,
                    "Smallest blob radius searched, in image pixels.",
                    2.0,
                    60.0,
                    1.0,
                ),
                ParamSpec(
                    "max_radius",
                    "Max radius (px)",
                    "float",
                    60.0,
                    "Largest blob radius searched, in image pixels.",
                    6.0,
                    200.0,
                    2.0,
                ),
                ParamSpec(
                    "min_strength",
                    "Min blob contrast",
                    "float",
                    0.9,
                    "Threshold on the score (see definition).",
                    0.2,
                    4.0,
                    0.05,
                ),
                ParamSpec(
                    "edge_ratio",
                    "Edge rejection ratio",
                    "float",
                    10.0,
                    "Max principal-curvature ratio; 0 disables the test.",
                    0.0,
                    30.0,
                    1.0,
                ),
                ParamSpec(
                    "polarity",
                    "Polarity",
                    "choice",
                    "both",
                    "Bright blobs (lit rock faces), dark blobs (shadows/pits) or both.",
                    choices=("both", "bright", "dark"),
                ),
                _ROI,
            ),
            limitations=(
                "Pebble fields produce many small candidates.",
                "Large rocks inside the rover's shadow are often missed (low local contrast).",
                "Radii are image pixels: apparent size depends on distance; no physical size.",
            ),
            score_definition="|DoG| × σ²/(k−1) ÷ std(CLAHE image): dimensionless blob contrast "
            "at the blob's own scale. Not a probability.",
            run=_run_blobs,
        ),
        MethodSpec(
            name="rocks_contour",
            title="Rock candidates — closed edge regions",
            category="detection",
            kind="algorithmic",
            summary="Canny edges on the CLAHE image are closed morphologically; resulting "
            "regions are "
            "kept if compact (area, solidity, aspect) and sharply outlined.",
            params=(
                ParamSpec(
                    "min_area",
                    "Min area (px²)",
                    "float",
                    120.0,
                    "Smallest region area in image pixels.",
                    10.0,
                    5000.0,
                    10.0,
                ),
                ParamSpec(
                    "max_area",
                    "Max area (px²)",
                    "float",
                    20000.0,
                    "Largest region area in image pixels.",
                    200.0,
                    100000.0,
                    100.0,
                ),
                ParamSpec(
                    "min_solidity",
                    "Min solidity",
                    "float",
                    0.75,
                    "Area ÷ convex-hull area; 1 = perfectly convex.",
                    0.3,
                    1.0,
                    0.05,
                ),
                ParamSpec(
                    "min_edge_strength",
                    "Min outline sharpness",
                    "float",
                    1.8,
                    "Threshold on the score (see definition).",
                    0.5,
                    6.0,
                    0.1,
                ),
                _ROI,
            ),
            limitations=(
                "Rocks touching each other merge into one region or are lost.",
                "Shadows with sharp outlines can pass the shape filters.",
                "Areas are image pixels: no physical size.",
            ),
            score_definition="Mean gradient magnitude along the region outline ÷ median image "
            "gradient: how much sharper the outline is than typical texture. Not a probability.",
            run=_run_contours,
        ),
        MethodSpec(
            name="texture",
            title="Texture classes (unsupervised)",
            category="segmentation",
            kind="algorithmic",
            summary="k-means on per-tile texture statistics, ranked from smoothest to most "
            "textured.",
            params=(
                ParamSpec("tile", "Tile size (px)", "int", 16, "Analysis block size.", 8, 48, 8),
                ParamSpec("k", "Classes", "int", 3, "Number of clusters.", 2, 5, 1),
                ParamSpec(
                    "relative",
                    "Illumination-normalised",
                    "bool",
                    True,
                    "Divide texture by local brightness. Off: texture follows lighting.",
                ),
                ParamSpec(
                    "noise_floor",
                    "Noise floor (DN)",
                    "float",
                    NOISE_FLOOR,
                    "Added to brightness before normalising; damps sensor noise in shadows.",
                    0.0,
                    64.0,
                    2.0,
                ),
            ),
            limitations=(
                "Classes are NOT geological units (sand, bedrock…) — only relative texture.",
                "Single raw 8-bit image: absolute features follow illumination, relative features "
                "amplify noise in shadows. Shadow boundaries tend to fall in the most textured "
                "class.",
            ),
            run=_run_texture,
            experimental=True,
        ),
        MethodSpec(
            name="keypoints",
            title="ORB keypoints",
            category="features",
            kind="algorithmic",
            summary="Oriented FAST corners with rotation-aware BRIEF descriptors — the features "
            "used "
            "for matching images and, later, visual odometry.",
            params=(
                ParamSpec(
                    "n_features",
                    "Max keypoints",
                    "int",
                    1500,
                    "Upper bound on keypoints.",
                    100,
                    5000,
                    100,
                ),
            ),
            limitations=("Keypoints cluster on high-contrast texture; smooth sand yields few.",),
            run=_run_keypoints,
        ),
    )
}


def get_method(name: str) -> MethodSpec:
    spec = METHODS.get(name)
    if spec is None:
        raise InvalidRequestError(f"unknown method {name!r}; known: {sorted(METHODS)}")
    return spec
