"""``mars-terrain`` CLI.

uv run mars-terrain fetch     # download the PLACES 1 m DEM (~325 MB, resumable)
uv run mars-terrain status    # coverage + validation against real rover localizations
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Sequence

from mars_explorer.core.config import get_settings
from mars_explorer.core.logging import configure_logging
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.http import make_http_client
from mars_explorer.terrain.dem import PLACES_DEM
from mars_explorer.terrain.fetch import download_resumable
from mars_explorer.terrain.service import TerrainService


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mars-terrain", description="Orbital terrain tools.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download the PLACES orbital DEM (~325 MB, resumable)")
    sub.add_parser("status", help="show DEM coverage and georeferencing validation")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    service = TerrainService(settings, make_engine(settings.database_path))

    if args.command == "fetch":
        last = [0.0]

        def progress(done: int, total: int | None) -> None:
            if time.monotonic() - last[0] > 2:
                last[0] = time.monotonic()
                print(f"  {done / 1e6:6.0f} / {(total or 0) / 1e6:.0f} MB", flush=True)

        print("Downloading the Mars 2020 PLACES orbital DEM (NASA/JPL-Caltech, PDS)...")
        with make_http_client(settings) as http:
            download_resumable(
                http, settings.places_dem_label_url, service.dem_path.with_suffix(".xml")
            )
            download_resumable(
                http,
                settings.places_dem_url,
                service.dem_path,
                expected_size=PLACES_DEM.nbytes,
                progress=progress,
            )
        print(f"Done: {service.dem_path}")

    status = service.status()
    if not status["available"]:
        print("DEM not available. Run: uv run mars-terrain fetch")
        return 1
    v = status.get("validation", {})
    elevation = status.get("elevation_m", {})
    print(f"DEM            : {status['cols']} x {status['rows']} px at {status['cell_m']} m")
    print(f"Elevation      : {elevation.get('min', 0):.0f} to {elevation.get('max', 0):.0f} m")
    print(
        f"Validation     : {v.get('compared', 0)} of {v.get('waypoints', 0)} real localizations; "
        f"median offset {v.get('median_offset_m')} m, 95% within {v.get('p95_abs_offset_m')} m"
    )
    service.overview_path()
    print("Overview image : ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
