from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from mars_explorer.core.config import Settings
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.service import ImageSelection, IngestService
from tests.conftest import JPEG_BYTES, FakeNasa

NAVCAM_ID = "NLG_2024_0846620381_164ECM_N0930000NCAM00518_00_2I3J"


@pytest.fixture
def seeded(settings: Settings, fake_nasa: FakeNasa) -> Engine:
    engine = make_engine(settings.database_path)
    with httpx.Client(transport=httpx.MockTransport(fake_nasa)) as http:
        service = IngestService(engine, settings, http, sleep=lambda _: None)
        service.ingest_images([ImageSelection(sol_min=0, sol_max=5000)], sizes=("small",))
        service.ingest_waypoints()
    return engine


def test_health_and_mission(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    mission = client.get("/api/mission").json()
    assert mission["rover"] == "Perseverance"
    assert mission["landing_date"] == "2021-02-18"
    assert mission["provenance"] == "real_observation"
    assert mission["sources"][0]["url"].startswith("https://")


def test_empty_database_states(client: TestClient) -> None:
    assert client.get("/api/images").json() == {"items": [], "total": 0, "limit": 50, "offset": 0}
    assert client.get("/api/sols").json() == []
    position = client.get("/api/rover/position")
    assert position.status_code == 503
    assert position.json()["error"]["code"] == "no_position_data"
    status = client.get("/api/system/status").json()
    assert status["database"] == {"images": 0, "sols": 0, "waypoints": 0}
    assert status["last_ingest"] is None and status["feed"] is None


@pytest.mark.usefixtures("seeded")
def test_list_filters_and_pagination(client: TestClient) -> None:
    page = client.get("/api/images").json()
    assert page["total"] == 10
    sols = [item["sol"] for item in page["items"]]
    assert sols == sorted(sols, reverse=True)
    first = page["items"][0]
    assert first["thumb_url"] == f"/api/images/{first['image_id']}/file/small"
    assert first["date_taken_utc"].endswith("Z")
    assert first["provenance"] == "real_observation"

    assert client.get("/api/images", params={"sol": 1502}).json()["total"] == 3
    assert client.get("/api/images", params={"camera": "MCZ_LEFT"}).json()["total"] == 3
    both = client.get("/api/images", params=[("camera", "MCZ_LEFT"), ("camera", "NAVCAM_LEFT")])
    assert both.json()["total"] == 7
    assert client.get("/api/images", params={"group": "hazcam_front"}).json()["total"] == 3
    assert client.get("/api/images", params={"sol_min": 2000, "sol_max": 2030}).json()["total"] == 7

    paged = client.get("/api/images", params={"limit": 4, "offset": 8}).json()
    assert len(paged["items"]) == 2 and paged["offset"] == 8
    asc = client.get("/api/images", params={"order": "asc"}).json()["items"]
    assert asc[0]["sol"] == 1502

    bad = client.get("/api/images", params={"limit": 0})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_request"


@pytest.mark.usefixtures("seeded")
def test_detail(client: TestClient) -> None:
    detail = client.get(f"/api/images/{NAVCAM_ID}").json()
    assert detail["camera"] == {
        "instrument": "NAVCAM_LEFT",
        "group": "navcam",
        "label": "Navigation Camera — left (Navcam)",
    }
    assert detail["lmst"] == "12:35:01"
    assert detail["sequence_id"] == "NCAM00518"
    assert detail["filter_name"] is None
    assert detail["scale_factor"] == 4.0
    assert detail["local_files"] == {"small": True, "large": False, "full_res": False}
    assert detail["source"]["nasa_page_url"].endswith(NAVCAM_ID)
    assert any("Uncalibrated" in note for note in detail["notes"])
    assert any("Downsampled" in note for note in detail["notes"])

    missing = client.get("/api/images/NOPE")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "image_not_found"


@pytest.mark.usefixtures("seeded")
def test_file_serving_cached_and_on_demand(client: TestClient, fake_nasa: FakeNasa) -> None:
    cached = client.get(f"/api/images/{NAVCAM_ID}/file/small")
    assert cached.status_code == 200
    assert cached.headers["content-type"] == "image/jpeg"
    assert cached.content == JPEG_BYTES

    before = len(fake_nasa.requests)
    fetched = client.get(f"/api/images/{NAVCAM_ID}/file/large")
    assert fetched.status_code == 200 and fetched.content == JPEG_BYTES
    assert len(fake_nasa.requests) == before + 1
    again = client.get(f"/api/images/{NAVCAM_ID}/file/large")
    assert again.status_code == 200 and len(fake_nasa.requests) == before + 1

    assert client.get(f"/api/images/{NAVCAM_ID}/file/huge").status_code == 422
    assert client.get("/api/images/NOPE/file/small").status_code == 404


@pytest.mark.usefixtures("seeded")
def test_file_upstream_failure_is_502(client: TestClient, fake_nasa: FakeNasa) -> None:
    fake_nasa.fail_files = True
    response = client.get(f"/api/images/{NAVCAM_ID}/file/full_res")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_unavailable"


@pytest.mark.usefixtures("seeded")
def test_cameras_and_sols(client: TestClient) -> None:
    cameras = client.get("/api/cameras").json()
    assert len(cameras) == 24
    counts = {c["instrument"]: c["image_count"] for c in cameras}
    assert counts["NAVCAM_LEFT"] == 4 and counts["MCZ_LEFT"] == 3 and counts["SKYCAM"] == 0
    assert cameras[0]["group"] == "navcam"

    sols = client.get("/api/sols").json()
    assert [s["sol"] for s in sols] == [2024, 1502]
    assert sols[0]["image_count"] == 7
    assert sols[0]["instruments"] == ["MCZ_LEFT", "NAVCAM_LEFT"]
    assert sols[0]["earliest_utc"].endswith("Z")


@pytest.mark.usefixtures("seeded")
def test_rover_position_and_waypoints(client: TestClient) -> None:
    position = client.get("/api/rover/position").json()
    assert position["sol"] == 2022
    assert position["lat"] == pytest.approx(18.43559434)
    assert position["elevation_m"] == pytest.approx(-1936.366943)
    assert position["odometry_total_m"] == pytest.approx(45245.71)
    assert position["provenance"] == "real_observation"
    assert "M20_waypoints.json" in position["source"]["url"]
    assert position["source"]["retrieved_at"].endswith("Z")
    assert position["caveats"]

    waypoints = client.get("/api/rover/waypoints").json()
    assert len(waypoints["items"]) == 6
    sols = [w["sol"] for w in waypoints["items"]]
    assert sols == sorted(sols)


@pytest.mark.usefixtures("seeded")
def test_system_status(client: TestClient) -> None:
    status = client.get("/api/system/status").json()
    assert status["database"] == {"images": 10, "sols": 2, "waypoints": 6}
    assert status["storage"]["image_files"] == 10
    assert status["storage"]["bytes"] == 10 * len(JPEG_BYTES)
    assert status["last_ingest"]["kind"] == "waypoints"
    assert status["feed"]["latest_sol"] == 2031
