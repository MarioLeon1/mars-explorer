"""Contract v1.2 (Perception) over the HTTP API, with synthetic scenes of known ground truth."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from mars_explorer.core.config import Settings
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.service import ImageSelection, IngestService
from tests.conftest import FakeNasa
from tests.vision_scenes import ROCKS, SIZE, encode, rock_scene

NAVCAM = "NLG_2024_0846620381_164ECM_N0930000NCAM00518_00_2I3J"


@pytest.fixture
def seeded(settings: Settings, fake_nasa: FakeNasa) -> Engine:
    fake_nasa.image_bytes = encode(rock_scene())
    engine = make_engine(settings.database_path)
    with httpx.Client(transport=httpx.MockTransport(fake_nasa)) as http:
        service = IngestService(engine, settings, http, sleep=lambda _: None)
        service.ingest_images([ImageSelection(sol_min=0, sol_max=5000)], sizes=("small", "large"))
        service.ingest_image_ids(
            [fake_nasa.stereo_left["imageid"], fake_nasa.stereo_right["imageid"]]
        )
    return engine


def _analyze(client: TestClient, method: str, **params: object) -> dict:
    response = client.post(
        "/api/vision/analyses", json={"image_id": NAVCAM, "method": method, "params": params}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_methods_catalogue(client: TestClient) -> None:
    methods = {m["name"]: m for m in client.get("/api/vision/methods").json()}
    assert set(methods) == {"clahe", "edges", "rocks_blob", "rocks_contour", "texture", "keypoints"}
    assert methods["rocks_blob"]["produces_detections"] is True
    assert methods["rocks_blob"]["score_definition"]
    assert methods["texture"]["experimental"] is True
    assert all(m["kind"] == "algorithmic" and m["limitations"] for m in methods.values())
    polarity = next(p for p in methods["rocks_blob"]["params"] if p["name"] == "polarity")
    assert polarity["choices"] == ["both", "bright", "dark"]


@pytest.mark.usefixtures("seeded")
def test_analysis_is_derived_cached_and_serves_layers(
    client: TestClient, settings: Settings
) -> None:
    first = _analyze(client, "rocks_contour")
    assert first["provenance"] == "derived" and first["method_kind"] == "algorithmic"
    assert (first["width"], first["height"]) == (SIZE[1], SIZE[0])
    assert first["detections"] and first["stats"]["candidates"] == len(first["detections"])
    assert first["limitations"] and first["score_definition"]
    layer = client.get(first["layers"][0]["url"])
    assert layer.status_code == 200 and layer.headers["content-type"] == "image/png"

    second = _analyze(client, "rocks_contour")
    assert second["id"] == first["id"]
    assert second["created_at"] == first["created_at"]  # served from cache, not recomputed

    different = _analyze(client, "rocks_contour", min_area=300)
    assert different["id"] != first["id"]
    assert client.get(f"/api/vision/analyses/{first['id']}").json()["id"] == first["id"]


@pytest.mark.usefixtures("seeded")
def test_every_method_runs_through_the_api(client: TestClient) -> None:
    for method in ("clahe", "edges", "rocks_blob", "texture", "keypoints"):
        result = _analyze(client, method)
        assert result["timings_ms"]
        if method in {"clahe", "edges", "texture", "keypoints"}:
            assert result["layers"] and result["detections"] is None


@pytest.mark.usefixtures("seeded")
def test_validation_errors(client: TestClient) -> None:
    def post(body: dict) -> httpx.Response:
        return client.post("/api/vision/analyses", json=body)

    assert post({"image_id": NAVCAM, "method": "magic"}).status_code == 422
    bad = post({"image_id": NAVCAM, "method": "rocks_blob", "params": {"min_radius": 999}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_request"
    swapped = post(
        {"image_id": NAVCAM, "method": "rocks_blob", "params": {"min_radius": 30, "max_radius": 10}}
    )
    assert swapped.status_code == 422
    assert post({"image_id": "NOPE", "method": "clahe"}).status_code == 404
    assert client.get("/api/vision/analyses/nope").status_code == 404
    assert client.get("/api/vision/analyses/nope/layers/../../x.png").status_code == 404


@pytest.mark.usefixtures("seeded")
def test_annotations_and_evaluation(client: TestClient) -> None:
    width, height = SIZE[1], SIZE[0]
    ids = []
    for x, y, _ in ROCKS:
        created = client.post(
            f"/api/images/{NAVCAM}/annotations", json={"x": x / width, "y": y / height}
        )
        assert created.status_code == 201 and created.json()["provenance"] == "user_generated"
        ids.append(created.json()["id"])
    assert len(client.get(f"/api/images/{NAVCAM}/annotations").json()) == len(ROCKS)

    analysis = _analyze(client, "rocks_blob")
    evaluation = client.get(f"/api/vision/analyses/{analysis['id']}/evaluation").json()
    assert evaluation["annotations"] == len(ROCKS)
    assert evaluation["recall"] == 1.0
    assert 0 < evaluation["precision"] <= 1
    assert evaluation["caveats"]

    assert client.delete(f"/api/annotations/{ids[0]}").status_code == 204
    assert client.delete(f"/api/annotations/{ids[0]}").status_code == 404
    again = client.get(f"/api/vision/analyses/{analysis['id']}/evaluation").json()
    assert again["annotations"] == len(ROCKS) - 1

    texture = _analyze(client, "texture")
    assert client.get(f"/api/vision/analyses/{texture['id']}/evaluation").status_code == 422
    out_of_range = client.post(f"/api/images/{NAVCAM}/annotations", json={"x": 1.5, "y": 0.2})
    assert out_of_range.status_code == 422


def test_stereo_match_flags_verified_pairs(
    client: TestClient, seeded: Engine, fake_nasa: FakeNasa
) -> None:
    left, right = fake_nasa.stereo_left["imageid"], fake_nasa.stereo_right["imageid"]
    result = client.post("/api/vision/match", json={"image_a": left, "image_b": right}).json()
    assert result["stereo_pair"] is True
    assert result["inliers"] > 50  # same synthetic scene served for both
    assert result["disparity"]["dx_median_px"] == pytest.approx(0, abs=0.5)
    assert result["provenance"] == "derived" and result["notes"]
    other = client.post("/api/vision/match", json={"image_a": left, "image_b": NAVCAM}).json()
    assert other["stereo_pair"] is False
    same = client.post("/api/vision/match", json={"image_a": left, "image_b": left})
    assert same.status_code == 422


@pytest.mark.usefixtures("seeded")
def test_benchmark_runs_both_detectors(client: TestClient) -> None:
    for x, y, _ in ROCKS[:3]:
        client.post(f"/api/images/{NAVCAM}/annotations", json={"x": x / SIZE[1], "y": y / SIZE[0]})
    report = client.post(
        "/api/vision/benchmark", json={"cameras": ["NAVCAM_LEFT"], "limit": 10}
    ).json()
    assert report["images"] == 5  # 4 NAVCAM_LEFT from sol 2024 + the sol 2022 stereo left
    assert [m["method"] for m in report["methods"]] == ["rocks_blob", "rocks_contour"]
    blob = report["methods"][0]
    assert blob["runtime_ms"]["mean"] > 0 and blob["candidates"]["mean"] > 0
    assert blob["annotated_images"] == 1 and blob["recall"] is not None
    assert report["agreement_f1"] is not None and report["notes"]
    bad = client.post("/api/vision/benchmark", json={"cameras": ["NOPE"]})
    assert bad.status_code == 422
