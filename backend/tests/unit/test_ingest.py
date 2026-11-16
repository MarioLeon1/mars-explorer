from __future__ import annotations

import hashlib
import json

from sqlalchemy import Engine, func
from sqlmodel import Session, select

from mars_explorer.core.config import Settings
from mars_explorer.db.models import FeedStatus, ImageFile, ImageRecord, Waypoint
from mars_explorer.ingest.service import ImageSelection, IngestService
from mars_explorer.ingest.waypoints import parse_waypoints
from tests.conftest import JPEG_BYTES, FakeNasa, load_fixture

ALL = [ImageSelection(sol_min=0, sol_max=5000)]


def _count(engine: Engine, model: type) -> int:
    with Session(engine) as session:
        return session.exec(select(func.count()).select_from(model)).one()


def test_ingest_downloads_files_and_preserves_metadata(
    service: IngestService, engine: Engine, settings: Settings
) -> None:
    run = service.ingest_images(ALL)
    assert run.status == "success"
    assert run.items_added == 10 and run.files_downloaded == 20
    assert _count(engine, ImageRecord) == 10
    with Session(engine) as session:
        file = session.exec(select(ImageFile)).first()
        assert file is not None
        path = settings.data_dir / file.path
        assert path.read_bytes() == JPEG_BYTES
        assert file.sha256 == hashlib.sha256(JPEG_BYTES).hexdigest()
        assert file.content_type == "image/jpeg"  # NASA sends non-standard "image/jpg"
        metadata = json.loads((path.parent / "metadata.json").read_text(encoding="utf-8"))
        assert metadata["imageid"] == file.image_id
        assert session.get(FeedStatus, 1).latest_sol == 2031  # type: ignore[union-attr]
    assert not list(settings.data_dir.rglob("*.part"))  # atomic writes leave no temp files


def test_reingest_is_idempotent(service: IngestService, fake_nasa: FakeNasa) -> None:
    service.ingest_images(ALL)
    downloads_before = sum("/mars2020-raw-images/" in r.url.path for r in fake_nasa.requests)
    second = service.ingest_images(ALL)
    downloads_after = sum("/mars2020-raw-images/" in r.url.path for r in fake_nasa.requests)
    assert second.items_added == 0 and second.items_skipped == 10
    assert second.files_downloaded == 0 and second.files_skipped == 20
    assert downloads_after == downloads_before


def test_deleted_file_is_downloaded_again(
    service: IngestService, engine: Engine, settings: Settings
) -> None:
    service.ingest_images(ALL)
    with Session(engine) as session:
        file = session.exec(select(ImageFile)).first()
        assert file is not None
        (settings.data_dir / file.path).unlink()
    run = service.ingest_images(ALL)
    assert run.files_downloaded == 1


def test_failed_downloads_are_recorded_not_fatal(
    service: IngestService, fake_nasa: FakeNasa
) -> None:
    fake_nasa.fail_files = True
    run = service.ingest_images(ALL)
    assert run.items_added == 10  # metadata still stored
    assert run.items_failed == 20 and run.status == "partial"
    assert run.error and "HTTP 404" in run.error


def test_feed_outage_marks_run_failed(service: IngestService, fake_nasa: FakeNasa) -> None:
    fake_nasa.feed_status = 503
    run = service.ingest_images(ALL)
    assert run.status == "failed"
    assert run.items_added == 0


def test_camera_selection_and_limit(service: IngestService, engine: Engine) -> None:
    run = service.ingest_images(
        [ImageSelection(sol_min=2024, sol_max=2024, instruments=("NAVCAM_LEFT",), limit=2)]
    )
    assert run.items_added == 2
    with Session(engine) as session:
        assert {r.instrument for r in session.exec(select(ImageRecord))} == {"NAVCAM_LEFT"}


def test_waypoint_parsing_handles_missing_sentinel() -> None:
    waypoints = parse_waypoints(load_fixture("mmgis_waypoints_sample.json"))
    assert len(waypoints) == 6
    latest = waypoints[-1]
    assert latest.sol == 2022 and latest.site == 93 and latest.drive == 0
    assert latest.odometry_total_m == 45245.71
    assert latest.final is True
    sample = {
        "features": [{"properties": {"sol": 5, "lat": 18.4, "lon": 77.4, "elev_geoid": -9999.0}}]
    }
    assert parse_waypoints(sample)[0].elevation_m is None


def test_mid_drive_zero_odometry_means_missing() -> None:
    # Real pattern from M20_waypoints.json: mid-drive fixes report dist_total_m = 0.0.
    def feature(sol: int, odo: float, dist: float, note: str) -> dict:
        props = {"sol": sol, "lat": 18.4, "lon": 77.4, "dist_total_m": odo, "dist_m": dist}
        return {"properties": {**props, "Note": note}}

    waypoints = parse_waypoints(
        {
            "features": [
                feature(13, 0.0, 0.0, "End-of-drive localization"),
                feature(335, 2840.469, 25.0, "End-of-drive localization"),
                feature(340, 0.0, 0.0, "Mid-drive localization"),
            ]
        }
    )
    assert waypoints[0].odometry_total_m == 0.0  # the first fix genuinely starts at zero
    assert waypoints[1].odometry_total_m == 2840.469
    assert waypoints[2].odometry_total_m is None
    assert waypoints[2].drive_distance_m is None


def test_waypoint_refresh_replaces_rows(service: IngestService, engine: Engine) -> None:
    assert service.ingest_waypoints().status == "success"
    assert service.ingest_waypoints().items_added == 6
    assert _count(engine, Waypoint) == 6
