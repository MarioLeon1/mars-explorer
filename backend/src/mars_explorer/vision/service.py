"""Perception orchestration: run, cache, evaluate, match and benchmark.

Analyses are cached by a hash of (image, method, rendition, params, algorithm version), so the
same request is never recomputed and a changed algorithm never serves stale results.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy import Engine
from sqlmodel import Session, select

from mars_explorer.core.config import Settings
from mars_explorer.core.errors import InvalidRequestError, NotFoundError, UpstreamError
from mars_explorer.db.models import Annotation, ImageFile, ImageRecord, VisionAnalysis
from mars_explorer.ingest.cameras import stereo_candidate_id
from mars_explorer.ingest.downloader import ImageDownloader, ImageSize
from mars_explorer.vision import ALGORITHM_VERSION
from mars_explorer.vision.evaluation import MatchCounts, Point, agreement, match_points
from mars_explorer.vision.features import disparity_stats, match_images
from mars_explorer.vision.methods import METHODS, MethodOutput, get_method
from mars_explorer.vision.ops import Gray, load_gray
from mars_explorer.vision.pathsketch import PathSketch, SketchParams, sketch_path

log = logging.getLogger(__name__)

DETECTORS: tuple[str, ...] = ("rocks_blob", "rocks_contour")
MAX_DRAWN_MATCHES = 300


def analysis_id(image_id: str, method: str, rendition: str, params: dict[str, Any]) -> str:
    payload = json.dumps(
        {
            "image": image_id,
            "method": method,
            "rendition": rendition,
            "params": params,
            "version": ALGORITHM_VERSION,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


@dataclass(slots=True)
class EvaluationResult:
    analysis_id: str
    annotations: int
    counts: MatchCounts
    tolerance_px: float


@dataclass(slots=True)
class MatchSummary:
    image_a: str
    image_b: str
    stereo_pair: bool
    width_a: int
    height_a: int
    width_b: int
    height_b: int
    keypoints_a: int
    keypoints_b: int
    tentative: int
    inliers: int
    disparity: dict[str, float]
    drawn: list[dict[str, float | bool]]
    elapsed_ms: float


@dataclass(slots=True)
class MethodBenchmark:
    method: str
    runtimes_ms: list[float] = field(default_factory=list)
    candidates: list[int] = field(default_factory=list)
    counts: MatchCounts = field(default_factory=lambda: MatchCounts(0, 0, 0))
    annotated_images: int = 0


@dataclass(slots=True)
class BenchmarkReport:
    images: list[str]
    cameras: list[str]
    methods: list[MethodBenchmark]
    agreement: list[float]


class VisionService:
    def __init__(self, engine: Engine, settings: Settings, downloader: ImageDownloader) -> None:
        self._engine = engine
        self._settings = settings
        self._downloader = downloader

    # ---- paths & loading -----------------------------------------------------------------

    def layer_dir(self, analysis: str) -> Path:
        return self._settings.data_dir / "derived" / "vision" / analysis

    def layer_path(self, analysis: str, layer: str) -> Path:
        if not layer.replace("_", "").isalnum():
            raise NotFoundError(f"no layer {layer!r}", code="layer_not_found")
        return self.layer_dir(analysis) / f"{layer}.png"

    def _load(self, session: Session, image_id: str, rendition: ImageSize) -> Gray:
        image = session.get(ImageRecord, image_id)
        if image is None:
            raise NotFoundError(f"No ingested image with id {image_id!r}", code="image_not_found")
        result = self._downloader.ensure(session, image, rendition)
        if result.file is None:
            raise UpstreamError(f"could not fetch {rendition} of {image_id}: {result.error}")
        return load_gray(self._downloader.absolute(result.file))

    # ---- analyses --------------------------------------------------------------------------

    def analyze(
        self, image_id: str, method: str, params: dict[str, Any] | None, rendition: ImageSize
    ) -> VisionAnalysis:
        spec = get_method(method)
        resolved = spec.resolve(params)
        key = analysis_id(image_id, method, rendition, resolved)
        with Session(self._engine) as session:
            cached = session.get(VisionAnalysis, key)
            if cached is not None and all(
                self.layer_path(key, layer["name"]).is_file() for layer in cached.layers
            ):
                return cached
            gray = self._load(session, image_id, rendition)

        output = MethodOutput()
        spec.run(gray, resolved, output)
        directory = self.layer_dir(key)
        directory.mkdir(parents=True, exist_ok=True)
        for layer in output.layers:
            ok, encoded = cv2.imencode(".png", cv2.cvtColor(layer.rgba, cv2.COLOR_RGBA2BGRA))
            if not ok:
                raise RuntimeError(f"PNG encoding failed for layer {layer.name}")
            target = self.layer_path(key, layer.name)
            tmp = target.with_suffix(".part")
            tmp.write_bytes(encoded.tobytes())
            os.replace(tmp, target)

        record = VisionAnalysis(
            id=key,
            image_id=image_id,
            method=method,
            rendition=rendition,
            params=resolved,
            algorithm_version=ALGORITHM_VERSION,
            width=int(gray.shape[1]),
            height=int(gray.shape[0]),
            timings_ms=output.timings_ms,
            stats=output.stats,
            detections=None
            if output.detections is None
            else [
                {
                    "x": round(c.x, 2),
                    "y": round(c.y, 2),
                    "r": round(c.r, 2),
                    "score": round(c.score, 4),
                    "area_px": round(c.area_px, 1),
                }
                for c in output.detections
            ],
            layers=[{"name": layer.name, "label": layer.label} for layer in output.layers],
        )
        with Session(self._engine) as session:
            existing = session.get(VisionAnalysis, key)
            if existing is not None:
                session.delete(existing)
                session.flush()
            session.add(record)
            session.commit()
            session.refresh(record)
        log.info("vision %s on %s: %s ms", method, image_id, output.timings_ms)
        return record

    def path_sketch(
        self,
        image_id: str,
        goal: tuple[float, float],
        start: tuple[float, float] | None,
        params: SketchParams,
        rendition: ImageSize = "large",
    ) -> PathSketch:
        """Image-space path around rock candidates (derived, illustrative; see pathsketch)."""
        with Session(self._engine) as session:
            gray = self._load(session, image_id, rendition)
        return sketch_path(gray, goal, start, params)

    def get(self, analysis: str) -> VisionAnalysis:
        with Session(self._engine) as session:
            record = session.get(VisionAnalysis, analysis)
        if record is None:
            raise NotFoundError(f"No analysis {analysis!r}", code="analysis_not_found")
        return record

    # ---- evaluation ------------------------------------------------------------------------

    def evaluate(self, analysis: str) -> EvaluationResult:
        record = self.get(analysis)
        if record.detections is None:
            raise InvalidRequestError(f"{record.method} does not produce detections")
        with Session(self._engine) as session:
            notes = session.exec(
                select(Annotation).where(Annotation.image_id == record.image_id)
            ).all()
        truth = [Point(a.x * record.width, a.y * record.height) for a in notes]
        detections = [Point(d["x"], d["y"], d["r"]) for d in record.detections]
        return EvaluationResult(
            analysis_id=record.id,
            annotations=len(truth),
            counts=match_points(detections, truth, record.width),
            tolerance_px=round(0.015 * record.width, 1),
        )

    # ---- stereo / pair matching -------------------------------------------------------------

    def match(self, image_a: str, image_b: str, rendition: ImageSize) -> MatchSummary:
        if image_a == image_b:
            raise InvalidRequestError("choose two different images")
        with Session(self._engine) as session:
            gray_a = self._load(session, image_a, rendition)
            gray_b = self._load(session, image_b, rendition)
            record_a = session.get(ImageRecord, image_a)
        start = time.perf_counter()
        result = match_images(gray_a, gray_b)
        elapsed = (time.perf_counter() - start) * 1000
        inliers = result.inliers
        outliers = [m for m in result.matches if not m.inlier]
        step = max(1, len(inliers) // MAX_DRAWN_MATCHES)
        drawn = inliers[::step][:MAX_DRAWN_MATCHES] + outliers[: MAX_DRAWN_MATCHES // 3]
        stereo = (
            record_a is not None and stereo_candidate_id(image_a, record_a.instrument) == image_b
        )
        return MatchSummary(
            image_a=image_a,
            image_b=image_b,
            stereo_pair=stereo,
            width_a=int(gray_a.shape[1]),
            height_a=int(gray_a.shape[0]),
            width_b=int(gray_b.shape[1]),
            height_b=int(gray_b.shape[0]),
            keypoints_a=result.keypoints_a,
            keypoints_b=result.keypoints_b,
            tentative=result.tentative,
            inliers=len(inliers),
            disparity={k: round(v, 2) for k, v in disparity_stats(inliers).items()},
            drawn=[
                {
                    "ax": round(m.ax, 1),
                    "ay": round(m.ay, 1),
                    "bx": round(m.bx, 1),
                    "by": round(m.by, 1),
                    "inlier": m.inlier,
                }
                for m in drawn
            ],
            elapsed_ms=round(elapsed, 1),
        )

    # ---- benchmark -------------------------------------------------------------------------

    def benchmark(self, cameras: Sequence[str], limit: int) -> BenchmarkReport:
        """Run both detectors (default parameters) on locally cached images; no downloads."""
        with Session(self._engine) as session:
            query = (
                select(ImageRecord.image_id, ImageFile.path)
                .join(ImageFile, ImageFile.image_id == ImageRecord.image_id)
                .where(ImageFile.size == "large")
                .order_by(ImageRecord.sol.desc(), ImageRecord.image_id)  # type: ignore[attr-defined]
                .limit(limit)
            )
            if cameras:
                query = query.where(ImageRecord.instrument.in_(cameras))  # type: ignore[attr-defined]
            rows = session.exec(query).all()
            annotations = session.exec(select(Annotation)).all()
        by_image: dict[str, list[Annotation]] = {}
        for note in annotations:
            by_image.setdefault(note.image_id, []).append(note)

        stats = {name: MethodBenchmark(name) for name in DETECTORS}
        agreements: list[float] = []
        used: list[str] = []
        for image_id, path in rows:
            try:
                gray = load_gray(self._settings.data_dir / path)
            except (OSError, ValueError) as exc:
                log.warning("benchmark: skipping %s (%s)", image_id, exc)
                continue
            used.append(image_id)
            height, width = gray.shape
            found: dict[str, list[Point]] = {}
            for name in DETECTORS:
                spec = METHODS[name]
                output = MethodOutput()
                spec.run(gray, spec.resolve({}), output)
                points = [Point(c.x, c.y, c.r) for c in output.detections or []]
                found[name] = points
                bench = stats[name]
                bench.runtimes_ms.append(sum(output.timings_ms.values()))
                bench.candidates.append(len(points))
                notes = by_image.get(image_id)
                if notes:
                    truth = [Point(n.x * width, n.y * height) for n in notes]
                    counts = match_points(points, truth, width)
                    bench.annotated_images += 1
                    bench.counts = MatchCounts(
                        bench.counts.true_positives + counts.true_positives,
                        bench.counts.false_positives + counts.false_positives,
                        bench.counts.false_negatives + counts.false_negatives,
                    )
            value = agreement(found[DETECTORS[0]], found[DETECTORS[1]], width)
            if value is not None:
                agreements.append(value)
        return BenchmarkReport(used, list(cameras), list(stats.values()), agreements)


def summarize(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    ordered = sorted(values)
    return {
        "mean": round(statistics.fmean(ordered), 2),
        "median": round(statistics.median(ordered), 2),
        "p95": round(float(np.percentile(ordered, 95)), 2),
    }
