"""Contract v1.4 — Mission Replay endpoints over real captured feed + traverse fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from mars_explorer.api.app import create_app
from mars_explorer.core.config import Settings
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.service import ImageSelection, IngestService
from tests.conftest import FakeNasa


@pytest.fixture
def replay_client(settings: Settings, fake_nasa: FakeNasa) -> Iterator[TestClient]:
    engine = make_engine(settings.database_path)
    with httpx.Client(transport=httpx.MockTransport(fake_nasa)) as http:
        service = IngestService(engine, settings, http, sleep=lambda _: None)
        service.ingest_images([ImageSelection(sol_min=0, sol_max=5000)], sizes=())
        assert service.ingest_traverse().status == "success"
    app = create_app(settings, transport=httpx.MockTransport(fake_nasa))
    with TestClient(app) as client:
        yield client


def test_sequences_are_reconstructed_and_derived(replay_client: TestClient) -> None:
    items = replay_client.get("/api/replay/sequences").json()
    by_id = {s["id"]: s for s in items}
    assert "2024-NAVCAM_LEFT-NCAM00518" in by_id
    navcam = by_id["2024-NAVCAM_LEFT-NCAM00518"]
    assert navcam["frame_count"] == 4
    assert navcam["label"] == "reconstructed"
    assert navcam["provenance"] == "derived"
    assert navcam["kind"] in {"fixed_pointing", "pointing_sweep"}
    assert navcam["thumb_url"].startswith("/api/images/")
    # min_frames filter
    assert all(
        s["frame_count"] >= 4
        for s in replay_client.get("/api/replay/sequences", params={"min_frames": 4}).json()
    )
    assert replay_client.get("/api/replay/sequences", params={"sol": 1}).json() == []


def test_sequence_detail_frames_are_real_and_sclk_ordered(replay_client: TestClient) -> None:
    detail = replay_client.get("/api/replay/sequences/2024-NAVCAM_LEFT-NCAM00518").json()
    sclks = [f["sclk"] for f in detail["frames"]]
    assert sclks == sorted(sclks)
    assert detail["frames"][0]["t_offset_s"] == 0
    assert all(f["provenance"] == "real_observation" for f in detail["frames"])
    assert detail["notes"][0].startswith("Reconstructed")
    assert "not a NASA video" in detail["notes"][0]
    assert detail["credits"] == ["NASA/JPL-Caltech"]
    assert detail["real_time_available"] is True
    assert detail["frames"][0]["preview_url"].endswith("/file/large")


@pytest.mark.parametrize("bad", ["nope", "2024-NAVCAM_LEFT-NCAM99999", "9-LCAM-LVS"])
def test_unknown_sequence_is_404(replay_client: TestClient, bad: str) -> None:
    response = replay_client.get(f"/api/replay/sequences/{bad}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_mission_timeline_combines_images_and_real_drives(replay_client: TestClient) -> None:
    body = replay_client.get("/api/replay/mission").json()
    sols = {s["sol"]: s for s in body["sols"]}
    assert {1108, 1109, 1110} <= set(sols)  # traverse fixture
    assert sols[2024]["images"] > 0 and sols[2024]["drives"] == 0
    assert sols[1108]["drives"] >= 1 and sols[1108]["drive_m"] > 0
    assert body["drive_sols"] == 3
    assert body["total_drive_m"] == pytest.approx(sum(s["drive_m"] for s in body["sols"]), abs=0.1)
    assert body["provenance"] == "real_observation"
    assert [s["sol"] for s in body["sols"]] == sorted(sols)


def test_sol_timeline_places_images_on_lmst(replay_client: TestClient) -> None:
    body = replay_client.get("/api/replay/sols/2024").json()
    assert body["images"]
    assert all(0 <= i["lmst_h"] < 25 for i in body["images"] if i["lmst_h"] is not None)
    assert body["lmst_calibration"]["samples"] > 0
    assert body["lmst_calibration"]["max_residual_s"] < 5  # LMST and SCLK agree
    assert body["drives"] == []
    assert body["previous_sol"] is not None and body["next_sol"] is None
    assert any(s["id"] == "2024-NAVCAM_LEFT-NCAM00518" for s in body["sequences"])


def test_sol_with_only_drives_cannot_place_drive_times(replay_client: TestClient) -> None:
    body = replay_client.get("/api/replay/sols/1108").json()
    assert body["images"] == []
    assert body["drives"] and body["drives"][0]["provenance"] == "real_observation"
    assert body["drives"][0]["start_lmst_h"] is None
    assert body["lmst_calibration"] is None
    assert any("cannot be placed" in n for n in body["notes"])
    assert replay_client.get("/api/replay/sols/77").status_code == 404


def test_featured_sequences_offer_an_ingest_job(replay_client: TestClient) -> None:
    items = replay_client.get("/api/replay/featured").json()
    assert {i["key"] for i in items} == {"landing-lcam", "sol2024-navcam-horizon"}
    landing = next(i for i in items if i["key"] == "landing-lcam")
    assert landing["published_frames"] == 87
    assert landing["local_frames"] == 0 and landing["sequence_url"] is None
    assert landing["job_request"] == {
        "sol_min": 0,
        "sol_max": 0,
        "cameras": ["LCAM"],
        "limit": 100,
        "full_res": False,
    }
    # The job body is accepted as-is by the ingest API.
    job = replay_client.post("/api/ingest/jobs", json=landing["job_request"])
    assert job.status_code == 202


def test_official_videos_are_labelled_with_credit(replay_client: TestClient) -> None:
    videos = replay_client.get("/api/replay/videos").json()
    assert len(videos) == 3
    for video in videos:
        assert video["label"] == "official_nasa_video"
        assert video["provenance"] == "real_observation"
        assert video["credit"].startswith("NASA/JPL-Caltech")
        assert video["video_url"].startswith("https://images-assets.nasa.gov/video/")
