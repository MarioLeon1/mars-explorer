"""Contract v1.3 (Terrain & Navigation) over HTTP, on a synthetic DEM in the PLACES layout."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from mars_explorer.api.app import create_app
from mars_explorer.core.config import Settings
from mars_explorer.db.session import make_engine
from mars_explorer.ingest.service import IngestService
from tests.conftest import FakeNasa
from tests.terrain_scenes import synthetic_elevation, synthetic_spec, write_dem

SPEC = synthetic_spec()


@pytest.fixture
def terrain_client(settings: Settings, fake_nasa: FakeNasa) -> Iterator[TestClient]:
    write_dem(settings.terrain_dir / "m20_orbital_dem.img", SPEC, synthetic_elevation(SPEC))
    engine = make_engine(settings.database_path)
    with httpx.Client(transport=httpx.MockTransport(fake_nasa)) as http:
        service = IngestService(engine, settings, http, sleep=lambda _: None)
        assert service.ingest_traverse().status == "success"
    app = create_app(settings, transport=httpx.MockTransport(fake_nasa), dem_spec=SPEC)
    with TestClient(app) as client:
        yield client


def centre() -> dict[str, float]:
    (e0, e1), (n0, n1) = SPEC.easting_range, SPEC.northing_range
    return {"e": (e0 + e1) / 2, "n": (n0 + n1) / 2}


def test_status_reports_real_observation_source(terrain_client: TestClient) -> None:
    status = terrain_client.get("/api/terrain/status").json()
    assert status["available"] is True and status["provenance"] == "real_observation"
    assert status["cols"] == SPEC.cols and status["cell_m"] == 1.0
    assert status["source"]["url"].startswith("https://pds-geosciences")
    overview = terrain_client.get("/api/terrain/overview.png")
    assert overview.status_code == 200 and overview.headers["content-type"] == "image/png"


def test_missing_dem_is_explained(client: TestClient) -> None:
    status = client.get("/api/terrain/status").json()
    assert status["available"] is False and "mars-terrain fetch" in status["how_to_get"]
    response = client.post("/api/terrain/maps", json={"center": {"e": 4.34e6, "n": 1.09e6}})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "terrain_not_available"


def test_drives_are_real_paths(terrain_client: TestClient) -> None:
    drives = terrain_client.get("/api/terrain/drives", params={"step_m": 0}).json()
    assert [d["sol"] for d in drives] == [1108, 1109, 1110]
    assert len(drives[0]["points"]) == 80
    thinned = terrain_client.get("/api/terrain/drives", params={"step_m": 10}).json()
    assert len(thinned[0]["points"]) < 80


def test_map_layers_stats_and_assumptions(terrain_client: TestClient) -> None:
    response = terrain_client.post("/api/terrain/maps", json={"center": centre(), "size_m": 900})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provenance"] == "derived" and body["assumptions"] and body["limitations"]
    assert body["size_m"] == 900 and body["cell_m"] == 3 and body["grid"] == [300, 300]
    assert body["extent"]["e_max"] - body["extent"]["e_min"] == 900
    assert {layer["name"] for layer in body["layers"]} == {
        "hillshade",
        "slope",
        "roughness",
        "risk",
    }
    risk = next(layer for layer in body["layers"] if layer["name"] == "risk")
    assert [item["label"] for item in risk["legend"]] == ["low", "moderate", "high", "impassable"]
    assert body["stats"]["risk_fraction"]["impassable"] > 0  # the mesa walls
    assert body["stats"]["slope_max_deg"] > 45
    png = terrain_client.get(risk["url"])
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    again = terrain_client.post(
        "/api/terrain/maps", json={"center": centre(), "size_m": 900}
    ).json()
    assert again["id"] == body["id"]  # deterministic id → cache
    stricter = {"center": centre(), "size_m": 900, "cost_model": {"max_slope_deg": 10}}
    assert terrain_client.post("/api/terrain/maps", json=stricter).json()["id"] != body["id"]


def mesa_points() -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Start west of the steep mesa, goal east of it, and a point ON the mesa top."""
    (e0, _), (_, n1) = SPEC.easting_range, SPEC.northing_range
    row = SPEC.rows * 0.5
    start = {"e": e0 + SPEC.cols * 0.55, "n": n1 - row}
    goal = {"e": e0 + SPEC.cols * 0.92, "n": n1 - row}
    top = {"e": e0 + SPEC.cols * 0.8, "n": n1 - row}
    return start, goal, top


def test_plan_compares_all_planners_and_explains(terrain_client: TestClient) -> None:
    start, goal, _ = mesa_points()
    request = {"map": {"center": centre(), "size_m": 800}, "start": start, "goal": goal}
    response = terrain_client.post("/api/navigation/plans", json=request)
    assert response.status_code == 200, response.text
    plan = response.json()
    routes = {r["planner"]: r for r in plan["routes"]}
    assert set(routes) == {"astar", "dijkstra", "theta_star", "rrt_star"}
    assert all(r["found"] and r["metrics"]["feasible"] for r in routes.values())
    assert routes["astar"]["metrics"]["cost"] == pytest.approx(
        routes["dijkstra"]["metrics"]["cost"]
    )
    assert routes["astar"]["expanded"] < routes["dijkstra"]["expanded"]
    assert routes["rrt_star"]["kind"] == "randomized" and routes["rrt_star"]["extra"]["seed"] == 42
    assert routes["astar"]["kind"] == "deterministic"
    assert plan["best"] in routes and plan["explanation"]
    for r in routes.values():
        assert r["metrics"]["max_slope_deg"] < 30  # never climbs the 63° mesa walls
        assert r["metrics"]["profile"] and r["points"][0] != r["points"][-1]
    assert plan["provenance"] == "derived" and plan["actual"] is None


def test_unreachable_goal_is_reported_by_every_planner(terrain_client: TestClient) -> None:
    start, _, top = mesa_points()  # the mesa top is ringed by 63° walls
    request = {"map": {"center": centre(), "size_m": 800}, "start": start, "goal": top}
    plan = terrain_client.post("/api/navigation/plans", json=request).json()
    assert plan["best"] is None
    assert all(not r["found"] and r["reason"] for r in plan["routes"])
    assert plan["explanation"] == ["No planner found a feasible route under this cost model."]


def test_replanning_a_real_drive_includes_the_actual_path(terrain_client: TestClient) -> None:
    request = {"map": {"drives": [0, 2], "margin_m": 100}, "planners": ["astar", "theta_star"]}
    plan = terrain_client.post("/api/navigation/plans", json=request).json()
    actual = plan["actual"]
    assert actual["kind"] == "real_observation" and actual["title"] == "Rover's actual drive"
    assert len(actual["points"]) == 80 + 25 + 34
    assert actual["metrics"]["length_m"] > 0
    assert any("real drive path" in line for line in plan["explanation"])
    first = actual["points"][0]
    assert abs(plan["start"]["e"] - first[0]) < 6 and abs(plan["start"]["n"] - first[1]) < 6


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (
            {
                "map": {"center": {"e": 0, "n": 0}},
                "start": {"e": 0, "n": 0},
                "goal": {"e": 1, "n": 1},
            },
            422,
        ),
        ({"map": {"center": "CENTRE", "size_m": 50}}, 422),
        (
            {
                "map": {"center": "CENTRE"},
                "planners": ["magic"],
                "start": "CENTRE",
                "goal": "CENTRE",
            },
            422,
        ),
        ({"map": {"center": "CENTRE"}}, 422),
        ({"map": {"drives": [2, 0]}}, 422),
        ({"map": {"drives": [0, 99]}}, 422),
    ],
)
def test_plan_validation(terrain_client: TestClient, body: dict, status: int) -> None:
    def fill(value: object) -> object:
        if value == "CENTRE":
            return centre()
        if isinstance(value, dict):
            return {k: fill(v) for k, v in value.items()}
        return value

    response = terrain_client.post("/api/navigation/plans", json=fill(body))
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == "invalid_request"
