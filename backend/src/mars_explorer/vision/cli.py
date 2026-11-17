"""``mars-vision`` CLI: reproducible perception benchmark over the local archive.

uv run mars-vision benchmark                          # Navcam + Hazcam, 40 images
uv run mars-vision benchmark --camera MCZ_LEFT --limit 20
"""

from __future__ import annotations

import argparse
import platform
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import cv2

from mars_explorer.core.config import REPO_ROOT, get_settings
from mars_explorer.core.logging import configure_logging
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.cameras import CATALOG
from mars_explorer.ingest.downloader import ImageDownloader
from mars_explorer.ingest.http import make_http_client
from mars_explorer.vision import ALGORITHM_VERSION
from mars_explorer.vision.methods import METHODS
from mars_explorer.vision.service import BenchmarkReport, VisionService, summarize

DEFAULT_CAMERAS = (
    "NAVCAM_LEFT",
    "NAVCAM_RIGHT",
    "FRONT_HAZCAM_LEFT_A",
    "FRONT_HAZCAM_RIGHT_A",
    "REAR_HAZCAM_LEFT",
)


def _fmt(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def render_report(report: BenchmarkReport, limit: int) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Perception benchmark — rock-candidate detectors",
        "",
        f"Generated {now} by `uv run mars-vision benchmark` "
        f"(algorithm version {ALGORITHM_VERSION}).",
        "",
        "## Dataset",
        "",
        f"- {len(report.images)} real Perseverance raw images from the local archive "
        f"(max {limit}), cameras: {', '.join(report.cameras) or 'all'}.",
        "- Rendition: NASA `large` JPEG (≈1200 px wide). Credit: NASA/JPL-Caltech.",
        "- Default parameters for every method (see `vision/methods.py`).",
        "",
        "## Results",
        "",
        "| Method | Images | Runtime ms (median / p95) | Candidates per image (median) "
        "| Annotated images | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for bench in report.methods:
        runtime = summarize(bench.runtimes_ms)
        candidates = summarize([float(c) for c in bench.candidates])
        counts = bench.counts
        lines.append(
            f"| {METHODS[bench.method].title} | {len(bench.runtimes_ms)} "
            f"| {_fmt(runtime and runtime['median'])} / {_fmt(runtime and runtime['p95'])} "
            f"| {_fmt(candidates and candidates['median'], 0)} | {bench.annotated_images} "
            f"| {_fmt(counts.precision, 2)} | {_fmt(counts.recall, 2)} | {_fmt(counts.f1, 2)} |"
        )
    agreement = summarize(report.agreement)
    lines += [
        "",
        f"Agreement between the two detectors (F1, median over images): "
        f"**{_fmt(agreement and agreement['median'], 2)}**.",
        "",
        "## How to read this",
        "",
        "- Runtime: this machine, single thread, image decoding excluded "
        f"({platform.processor() or platform.machine()}, OpenCV {cv2.__version__}).",
        "- Hybrid CPUs (e.g. Intel P-cores + E-cores): Windows may schedule this single-threaded, "
        "bursty work on efficiency cores. Measured on an i7-14700KF: blob detector 157 ms pinned "
        "to P-cores vs 342 ms pinned to E-cores. Compare methods within one run, not across runs.",
        "- Agreement is not accuracy: it shows how often the two independent methods point at the "
        "same places.",
        "- Precision/recall exist only for images annotated by hand in the Perception module, and "
        "assume every relevant rock in them was marked. Human annotation is interpretation, not "
        "mission-confirmed ground truth.",
        "- Candidates are image regions, not confirmed rocks; sizes are pixels, not metres.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mars-vision", description="Perception tools.")
    sub = parser.add_subparsers(dest="command", required=True)
    bench = sub.add_parser("benchmark", help="benchmark rock-candidate detectors")
    bench.add_argument("--camera", action="append", default=[], metavar="INSTRUMENT")
    bench.add_argument("--limit", type=int, default=40)
    bench.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "docs" / "benchmarks" / "perception-benchmark.md",
        help="Markdown report path",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    cameras = tuple(args.camera) or DEFAULT_CAMERAS
    unknown = [c for c in cameras if c not in CATALOG]
    if unknown:
        parser.error(f"unknown instrument(s): {', '.join(unknown)}")

    engine = make_engine(settings.database_path)
    with make_http_client(settings) as http:
        service = VisionService(engine, settings, ImageDownloader(http, settings))
        print(f"Benchmarking on up to {args.limit} cached images ({', '.join(cameras)})...")
        report = service.benchmark(cameras, args.limit)
    if not report.images:
        print("No cached images for these cameras. Run: uv run mars-ingest seed")
        return 1
    text = render_report(report, args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    # Console output stays ASCII (Windows consoles often cannot print the report's symbols).
    for bench in report.methods:
        runtime = summarize(bench.runtimes_ms)
        candidates = summarize([float(c) for c in bench.candidates])
        counts = bench.counts
        print(
            f"  {bench.method:<14} images={len(bench.runtimes_ms):>3}  "
            f"runtime_ms median={_fmt(runtime and runtime['median'])}  "
            f"candidates median={_fmt(candidates and candidates['median'], 0)}  "
            f"precision={_fmt(counts.precision, 2)} recall={_fmt(counts.recall, 2)} "
            f"(annotated images: {bench.annotated_images})"
        )
    agreement = summarize(report.agreement)
    print(f"  agreement F1 median={_fmt(agreement and agreement['median'], 2)}")
    print(f"Report written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
