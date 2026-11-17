"""``mars-ingest`` command-line interface.

Examples (run inside ``backend/``)::

    uv run mars-ingest seed
    uv run mars-ingest images --sol 2024 --camera NAVCAM_LEFT --limit 20
    uv run mars-ingest images --sol 900 --sol-max 910 --camera MCZ_LEFT --camera MCZ_RIGHT
    uv run mars-ingest waypoints
    uv run mars-ingest status
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from sqlalchemy import func
from sqlmodel import Session, select

from mars_explorer.core.config import Settings, get_settings
from mars_explorer.core.logging import configure_logging
from mars_explorer.db.models import (
    FeedStatus,
    ImageFile,
    ImageRecord,
    IngestRun,
    TraverseSegment,
    Waypoint,
)
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.cameras import CATALOG
from mars_explorer.ingest.downloader import ImageSize
from mars_explorer.ingest.http import make_http_client
from mars_explorer.ingest.seed import seed_selections
from mars_explorer.ingest.service import ImageSelection, IngestService


def _print_run(run: IngestRun) -> None:
    print(
        f"  -> {run.kind}: {run.status} | records seen {run.items_seen}, new {run.items_added}, "
        f"already stored {run.items_skipped}, failed {run.items_failed} | files downloaded "
        f"{run.files_downloaded}, already cached {run.files_skipped}"
    )
    if run.error:
        lines = run.error.splitlines()
        print(f"  first problems ({len(lines)} total):")
        for line in lines[:5]:
            print(f"    - {line}")


def _print_status(settings: Settings) -> None:
    engine = make_engine(settings.database_path)
    with Session(engine) as session:
        images = session.exec(select(func.count()).select_from(ImageRecord)).one()
        sols = session.exec(select(func.count(func.distinct(ImageRecord.sol)))).one()
        files = session.exec(select(func.count()).select_from(ImageFile)).one()
        size = session.exec(select(func.coalesce(func.sum(ImageFile.bytes), 0))).one()
        waypoints = session.exec(select(func.count()).select_from(Waypoint)).one()
        drives = session.exec(select(func.count()).select_from(TraverseSegment)).one()
        feed = session.get(FeedStatus, 1)
        last = session.exec(select(IngestRun).order_by(IngestRun.id.desc())).first()  # type: ignore[union-attr]
    print(f"Data directory : {settings.data_dir}")
    print(f"Images         : {images} records across {sols} sols")
    print(f"Cached files   : {files} ({size / 1_048_576:.1f} MB)")
    print(f"Waypoints      : {waypoints} real localizations")
    print(f"Drive paths    : {drives} real drives (JPL MMGIS traverse)")
    if feed:
        print(
            f"NASA feed      : latest sol {feed.latest_sol}, {feed.total_images} images "
            f"(checked {feed.checked_at:%Y-%m-%d %H:%M} UTC)"
        )
    if last:
        print(f"Last run       : {last.kind} -> {last.status} at {last.finished_at or 'running'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mars-ingest", description="Ingest real NASA Mars 2020 Perseverance data."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="curated starter set (~130 images) + rover localizations")
    images = sub.add_parser("images", help="ingest images for a sol or sol range")
    images.add_argument("--sol", type=int, required=True, help="sol (or first sol of a range)")
    images.add_argument("--sol-max", type=int, help="last sol of the range (inclusive)")
    images.add_argument(
        "--camera",
        action="append",
        default=[],
        metavar="INSTRUMENT",
        help="instrument id, repeatable (e.g. NAVCAM_LEFT, MCZ_LEFT)",
    )
    images.add_argument("--limit", type=int, default=50, help="max records (default 50)")
    images.add_argument("--full-res", action="store_true", help="also download full PNGs")
    sub.add_parser("waypoints", help="refresh real rover localizations + drive paths (JPL MMGIS)")
    sub.add_parser("status", help="show what is stored locally")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)

    if args.command == "status":
        _print_status(settings)
        return 0

    unknown = [c for c in getattr(args, "camera", []) if c not in CATALOG]
    if unknown:
        print(f"Unknown instrument(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Known: {', '.join(sorted(CATALOG))}", file=sys.stderr)
        return 2

    engine = make_engine(settings.database_path)
    with make_http_client(settings) as http:
        service = IngestService(engine, settings, http, progress=lambda m: print(f"  - {m}"))
        runs: list[IngestRun] = []
        if args.command == "seed":
            print("Seeding a curated set of real Perseverance images (NASA/JPL-Caltech)...")
            runs.append(service.ingest_images(seed_selections(), kind="seed"))
            runs.append(service.ingest_waypoints())
            runs.append(service.ingest_traverse())
        elif args.command == "images":
            sizes: tuple[ImageSize, ...] = (
                ("small", "large", "full_res") if args.full_res else ("small", "large")
            )
            selection = ImageSelection(
                args.sol, args.sol_max or args.sol, tuple(args.camera), args.limit
            )
            runs.append(service.ingest_images([selection], sizes=sizes))
        elif args.command == "waypoints":
            runs.append(service.ingest_waypoints())
            runs.append(service.ingest_traverse())

    print("\nSummary")
    for run in runs:
        _print_run(run)
    print()
    _print_status(settings)
    return 1 if all(run.status == "failed" for run in runs) else 0


if __name__ == "__main__":
    raise SystemExit(main())
