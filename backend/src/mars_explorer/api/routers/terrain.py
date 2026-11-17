"""Terrain (real orbital DEM + derived layers) and navigation (route planning) API."""

from __future__ import annotations

import math

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from mars_explorer.api import schemas
from mars_explorer.core.errors import InvalidRequestError
from mars_explorer.core.provenance import Provenance
from mars_explorer.navigation.metrics import TITLES, RouteMetrics
from mars_explorer.terrain.layers import ASSUMPTIONS, LIMITATIONS, CostModel
from mars_explorer.terrain.service import RouteOut, TerrainMap, TerrainService

router = APIRouter(tags=["terrain"])

LAYER_LABELS = {
    "hillshade": "Shaded relief (DEM)",
    "slope": "Slope",
    "roughness": "Roughness",
    "risk": "Risk class (planning cells)",
}
DEM_SOURCE = {
    "name": "Mars 2020 PLACES orbital DEM (m20_orbital_dem), PDS Geosciences Node",
    "url": "https://pds-geosciences.wustl.edu/m2020/urn-nasa-pds-mars2020_rover_places/",
    "credit": "NASA/JPL-Caltech",
}


def _svc(request: Request) -> TerrainService:
    return request.app.state.terrain


def _model(body: schemas.CostModelIn) -> CostModel:
    return CostModel(**body.model_dump())


def _map_out(service: TerrainService, terrain_map: TerrainMap) -> schemas.TerrainMapOut:
    drives = [
        d
        for d in service.drives()
        if any(
            terrain_map.e_min <= p[0] <= terrain_map.e_max
            and terrain_map.n_min <= p[1] <= terrain_map.n_max
            for p in d["points"]
        )
    ]
    return schemas.TerrainMapOut.model_validate(
        {
            "id": terrain_map.id,
            "center": {"e": terrain_map.center_e, "n": terrain_map.center_n},
            "size_m": terrain_map.size_m,
            "cell_m": terrain_map.cell_m,
            "grid": list(terrain_map.layers.cost.shape),
            "extent": {
                "e_min": terrain_map.e_min,
                "e_max": terrain_map.e_max,
                "n_min": terrain_map.n_min,
                "n_max": terrain_map.n_max,
            },
            "cost_model": terrain_map.model.as_dict(),
            "layers": [
                {
                    "name": name,
                    "label": label,
                    "url": f"/api/terrain/maps/{terrain_map.id}/layers/{name}.png",
                    "legend": terrain_map.legends.get(name, []),
                }
                for name, label in LAYER_LABELS.items()
            ],
            "stats": terrain_map.stats,
            "drives_in_view": drives,
            "provenance": Provenance.DERIVED,
            "assumptions": ASSUMPTIONS,
            "limitations": LIMITATIONS,
        }
    )


def _metrics_out(m: RouteMetrics | None) -> schemas.RouteMetricsOut | None:
    if m is None:
        return None
    return schemas.RouteMetricsOut(
        feasible=m.feasible,
        length_m=round(m.length_m, 1),
        impassable_m=round(m.impassable_m, 1),
        cost=round(m.cost, 1) if math.isfinite(m.cost) else None,
        cost_distance=round(m.cost_distance, 1),
        cost_slope=round(m.cost_slope, 1),
        cost_roughness=round(m.cost_roughness, 1),
        max_slope_deg=round(m.max_slope_deg, 2),
        mean_slope_deg=round(m.mean_slope_deg, 2),
        max_roughness_m=round(m.max_roughness_m, 3),
        elevation_gain_m=round(m.elevation_gain_m, 1),
        elevation_loss_m=round(m.elevation_loss_m, 1),
        min_clearance_m=round(m.min_clearance_m, 1) if m.min_clearance_m is not None else None,
        profile=[list(p) for p in m.profile],
    )


def _route_out(route: RouteOut) -> schemas.RouteOut:
    kind = {"rrt_star": "randomized", "actual": "real_observation"}.get(
        route.planner, "deterministic"
    )
    return schemas.RouteOut(
        planner=route.planner,
        title=TITLES[route.planner],
        kind=kind,  # type: ignore[arg-type]
        found=route.found,
        reason=route.reason,
        points=[[round(e, 1), round(n, 1)] for e, n in route.points],
        metrics=_metrics_out(route.metrics),
        expanded=route.expanded,
        elapsed_ms=route.elapsed_ms,
        extra=route.extra,
    )


@router.get("/terrain/status")
def terrain_status(request: Request) -> dict[str, object]:
    status = _svc(request).status()
    return {
        **status,
        "source": DEM_SOURCE,
        "provenance": Provenance.REAL_OBSERVATION,
        "notes": [
            "The DEM is a mission data product built from orbital stereo imagery; slope, "
            "roughness, "
            "risk and costs computed from it are derived.",
            "Validation compares JPL waypoint elevations with the DEM at the same coordinates.",
        ],
        "how_to_get": None if status["available"] else "cd backend; uv run mars-terrain fetch",
    }


@router.get(
    "/terrain/overview.png",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def terrain_overview(request: Request) -> FileResponse:
    return FileResponse(
        _svc(request).overview_path(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/terrain/drives", response_model=list[schemas.DrivePath])
def terrain_drives(request: Request, step_m: float = 10.0) -> list[schemas.DrivePath]:
    if not 0 <= step_m <= 100:
        raise InvalidRequestError("step_m must be within [0, 100]")
    return [schemas.DrivePath.model_validate(d) for d in _svc(request).drives(step_m)]


def _resolve_map(
    service: TerrainService, body: schemas.MapRequest
) -> tuple[TerrainMap, list[list[float]] | None]:
    model = _model(body.cost_model)
    if body.drives is not None:
        return service.map_for_drives(body.drives[0], body.drives[1], body.margin_m, model)
    if body.center is None:
        raise InvalidRequestError("give either a centre or a range of drives")
    return service.get_map(body.center.e, body.center.n, body.size_m, model), None


@router.post("/terrain/maps", response_model=schemas.TerrainMapOut)
def create_map(request: Request, body: schemas.MapRequest) -> schemas.TerrainMapOut:
    service = _svc(request)
    terrain_map, _ = _resolve_map(service, body)
    return _map_out(service, terrain_map)


@router.get(
    "/terrain/maps/{map_id}/layers/{layer}.png",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def map_layer(request: Request, map_id: str, layer: str) -> FileResponse:
    return FileResponse(
        _svc(request).layer_path(map_id, layer),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/navigation/plans", response_model=schemas.PlanOut)
def create_plan(request: Request, body: schemas.PlanRequest) -> schemas.PlanOut:
    service = _svc(request)
    terrain_map, drive_points = _resolve_map(service, body.map)
    start = (body.start.e, body.start.n) if body.start else None
    goal = (body.goal.e, body.goal.n) if body.goal else None
    if drive_points:  # replanning a real drive: default endpoints are the drive's own
        start = start or (drive_points[0][0], drive_points[0][1])
        goal = goal or (drive_points[-1][0], drive_points[-1][1])
    if start is None or goal is None:
        raise InvalidRequestError("start and goal are required (or plan over a range of drives)")
    plan = service.plan(
        terrain_map,
        start,
        goal,
        body.planners,
        rrt_seed=body.rrt_seed,
        rrt_iterations=body.rrt_iterations,
        actual_points=drive_points,
    )
    return schemas.PlanOut(
        map=_map_out(service, terrain_map),
        start=schemas.EN(e=plan.start[0], n=plan.start[1]),
        goal=schemas.EN(e=plan.goal[0], n=plan.goal[1]),
        snapped=plan.snapped,
        routes=[_route_out(r) for r in plan.routes],
        actual=_route_out(plan.actual) if plan.actual else None,
        best=plan.best,
        explanation=plan.explanation,
        provenance=Provenance.DERIVED,
    )
