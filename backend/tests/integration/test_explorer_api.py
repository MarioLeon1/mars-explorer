"""Contract v1.1 (Explorer): filters, chronology, relations, raw records, stereo, jobs."""

from __future__ import annotations

import time

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from mars_explorer.core.config import Settings
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.cameras import stereo_candidate_id
from mars_explorer.ingest.raw_feed import RawImagesClient
from mars_explorer.ingest.service import ImageSelection, IngestService
from tests.conftest import FakeNasa

NAVCAM_IDS_SOL2024 = [  # from raw_images_list_navcam_sol2024.json, feed order
    "NLG_2024_0846620381_164ECM_N0930000NCAM00518_00_2I3J",
]


@pytest.fixture
def seeded(settings: Settings, fake_nasa: FakeNasa) -> Engine:
    engine = make_engine(settings.database_path)
    with httpx.Client(transport=httpx.MockTransport(fake_nasa)) as http:
        IngestService(engine, settings, http, sleep=lambda _: None).ingest_images(
            [ImageSelection(sol_min=0, sol_max=5000)], sizes=("small",)
        )
    return engine


def _ids(page: dict) -> list[str]:
    return [item["image_id"] for item in page["items"]]


@pytest.mark.usefixtures("seeded")
def test_date_and_text_filters(client: TestClient) -> None:
    all_items = client.get("/api/images", params={"limit": 200}).json()["items"]
    dates = sorted({item["date_taken_utc"][:10] for item in all_items})
    first_day = dates[0]
    on_day = client.get("/api/images", params={"date_from": first_day, "date_to": first_day})
    assert on_day.status_code == 200
    assert {i["date_taken_utc"][:10] for i in on_day.json()["items"]} == {first_day}

    by_text = client.get("/api/images", params={"q": "ncam00518"}).json()
    assert by_text["total"] >= 1
    assert all("NCAM00518" in i["image_id"] for i in by_text["items"])
    # LIKE wildcards are escaped: '%' must not match everything
    assert client.get("/api/images", params={"q": "%"}).json()["total"] == 0
    assert client.get("/api/images", params={"date_from": "not-a-date"}).status_code == 422


@pytest.mark.usefixtures("seeded")
def test_neighbors_follow_chronology_within_filters(client: TestClient) -> None:
    asc = _ids(client.get("/api/images", params={"order": "asc", "limit": 200}).json())
    middle = asc[4]
    nb = client.get(f"/api/images/{middle}/neighbors").json()
    assert nb["position"] == 5 and nb["total"] == len(asc)
    assert nb["previous"]["image_id"] == asc[3]
    assert nb["next"]["image_id"] == asc[5]

    first = client.get(f"/api/images/{asc[0]}/neighbors").json()
    assert first["previous"] is None and first["position"] == 1
    last = client.get(f"/api/images/{asc[-1]}/neighbors").json()
    assert last["next"] is None

    filtered = client.get(f"/api/images/{middle}/neighbors", params={"camera": "MCZ_LEFT"}).json()
    if middle.startswith("ZL"):
        assert filtered["total"] == 3
    else:
        assert filtered["position"] is None  # current image is outside the filter

    assert client.get("/api/images/NOPE/neighbors").status_code == 404


@pytest.mark.usefixtures("seeded")
def test_related_and_raw(client: TestClient, fake_nasa: FakeNasa) -> None:
    image_id = NAVCAM_IDS_SOL2024[0]
    related = client.get(f"/api/images/{image_id}/related").json()
    assert all(i["image_id"] != image_id for i in related["same_sequence"])
    assert all(i["sol"] == 2024 for i in related["same_sequence"])
    assert related["stereo"] == {
        "partner_instrument": "NAVCAM_RIGHT",
        "candidate_id": "NRG" + image_id[3:],
        "local": None,
    }
    assert all(
        i["camera"]["instrument"] != "NAVCAM_LEFT" for i in related["same_sol_other_cameras"]
    )

    raw = client.get(f"/api/images/{image_id}/raw").json()
    original = fake_nasa.by_id[image_id]
    assert raw["record"] == original  # byte-for-byte the NASA record
    assert raw["provenance"] == "real_observation"

    mcz = next(r for r in fake_nasa.records if r["camera"]["instrument"] == "MCZ_LEFT")
    assert (
        client.get(f"/api/images/{mcz['imageid']}/related").json()["stereo"]["partner_instrument"]
        == "MCZ_RIGHT"
    )


def test_stereo_partner_is_fetched_only_when_published(
    client: TestClient, settings: Settings, fake_nasa: FakeNasa
) -> None:
    engine = make_engine(settings.database_path)
    with httpx.Client(transport=httpx.MockTransport(fake_nasa)) as http:
        service = IngestService(engine, settings, http, sleep=lambda _: None)
        service.ingest_image_ids([fake_nasa.stereo_left["imageid"]], sizes=("small",))
        service.ingest_images(
            [ImageSelection(sol_min=2024, sol_max=2024, instruments=("NAVCAM_LEFT",))],
            sizes=("small",),
        )

    left = fake_nasa.stereo_left["imageid"]
    response = client.post(f"/api/images/{left}/stereo-partner")
    assert response.status_code == 200
    partner = response.json()
    assert partner["image_id"] == fake_nasa.stereo_right["imageid"]
    assert partner["camera"]["instrument"] == "NAVCAM_RIGHT"
    related = client.get(f"/api/images/{left}/related").json()
    stereo = related["stereo"]
    assert stereo["local"]["image_id"] == partner["image_id"]
    # the partner is listed once (in `stereo`), not repeated in the other groups
    listed = [i["image_id"] for i in related["same_sequence"] + related["same_sol_other_cameras"]]
    assert partner["image_id"] not in listed
    # idempotent: second call returns the stored partner without a new feed request
    before = len(fake_nasa.requests)
    assert client.post(f"/api/images/{left}/stereo-partner").status_code == 200
    assert len(fake_nasa.requests) == before

    unpublished = NAVCAM_IDS_SOL2024[0]
    missing = client.post(f"/api/images/{unpublished}/stereo-partner")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "stereo_partner_not_found"


def test_fetch_by_id_ignores_the_feeds_silent_fallback(
    http: httpx.Client, settings: Settings
) -> None:
    client = RawImagesClient(http, settings, sleep=lambda _: None)
    assert client.fetch_by_id("NRG_2024_0846620381_164ECM_N0930000NCAM00518_00_2I3J") is None


def test_stereo_candidate_ids() -> None:
    assert stereo_candidate_id("NLG_2022_x", "NAVCAM_LEFT") == "NRG_2022_x"
    assert stereo_candidate_id("FRF_2022_x", "FRONT_HAZCAM_RIGHT_A") == "FLF_2022_x"
    assert stereo_candidate_id("ZL0_2022_x", "MCZ_LEFT") == "ZR0_2022_x"
    assert stereo_candidate_id("LRG_1_x", "SKYCAM") is None


def test_feed_availability_counts_published_and_stored(
    client: TestClient, fake_nasa: FakeNasa
) -> None:
    params = {"sol_min": 2024, "camera": "NAVCAM_LEFT"}
    first = client.get("/api/feed/availability", params=params).json()
    assert first["published"] == 4 and first["stored"] == 0
    assert first["source"]["url"].startswith("https://")
    requests = len(fake_nasa.requests)
    client.get("/api/feed/availability", params=params)  # cached for 10 min
    assert len(fake_nasa.requests) == requests
    bad = client.get("/api/feed/availability", params={"sol_min": 1, "camera": "NOPE"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_request"


def _wait_for(client: TestClient, job_id: str, timeout: float = 10) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/ingest/jobs/{job_id}").json()
        if job["status"] not in {"queued", "running"}:
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish")


def test_ingest_job_lifecycle(client: TestClient) -> None:
    created = client.post(
        "/api/ingest/jobs", json={"sol_min": 2024, "cameras": ["MCZ_LEFT"], "limit": 2}
    )
    assert created.status_code == 202
    job = _wait_for(client, created.json()["id"])
    assert job["status"] == "success"
    assert job["progress"]["added"] == 2 and job["progress"]["downloaded"] == 4
    assert job["run_id"] is not None and job["finished_at"].endswith("Z")
    assert client.get("/api/images", params={"camera": "MCZ_LEFT"}).json()["total"] == 2
    assert client.get("/api/ingest/jobs").json()[0]["id"] == job["id"]
    assert client.get("/api/system/status").json()["last_ingest"]["kind"] == "ui_job"


@pytest.mark.parametrize(
    "body",
    [
        {"sol_min": 10, "sol_max": 5},
        {"sol_min": 0, "sol_max": 100},
        {"sol_min": 1, "limit": 500},
        {"sol_min": 1, "cameras": ["NOT_A_CAMERA"]},
    ],
)
def test_ingest_job_validation(client: TestClient, body: dict) -> None:
    response = client.post("/api/ingest/jobs", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_unknown_job_is_404(client: TestClient) -> None:
    assert client.get("/api/ingest/jobs/nope").json()["error"]["code"] == "job_not_found"
