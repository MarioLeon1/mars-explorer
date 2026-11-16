"""Real rover localizations (JPL MMGIS)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlmodel import select

from mars_explorer.api import schemas
from mars_explorer.api.deps import SessionDep, SettingsDep
from mars_explorer.core.errors import NoDataError
from mars_explorer.core.provenance import Provenance
from mars_explorer.db.models import Waypoint

router = APIRouter(prefix="/rover", tags=["rover"])

CAVEATS = [
    "Localizations are published with a delay; the latest images may be newer than this position.",
    "Elevation is relative to the Mars areoid (reference surface), not to the landing site.",
]


def _source(url: str, retrieved_at: object) -> schemas.SourceRef:
    return schemas.SourceRef.model_validate(
        {
            "name": "JPL MMGIS — Perseverance localizations (M20_waypoints.json)",
            "url": url,
            "credit": "NASA/JPL-Caltech",
            "retrieved_at": retrieved_at,
        }
    )


def _ordered(session: SessionDep) -> list[Waypoint]:
    return list(
        session.exec(
            select(Waypoint).order_by(
                Waypoint.sol,
                Waypoint.site,
                Waypoint.drive,  # type: ignore[arg-type]
                Waypoint.source_index,
            )
        ).all()
    )


@router.get("/position", response_model=schemas.RoverPosition)
def position(session: SessionDep, settings: SettingsDep) -> schemas.RoverPosition:
    waypoints = _ordered(session)
    if not waypoints:
        raise NoDataError(
            "No rover localizations ingested yet. Run: uv run mars-ingest waypoints",
            code="no_position_data",
        )
    latest = waypoints[-1]
    return schemas.RoverPosition(
        sol=latest.sol,
        site=latest.site,
        drive=latest.drive,
        lat=latest.lat,
        lon=latest.lon,
        elevation_m=latest.elevation_m,
        roll_deg=latest.roll_deg,
        pitch_deg=latest.pitch_deg,
        yaw_deg=latest.yaw_deg,
        tilt_deg=latest.tilt_deg,
        drive_distance_m=latest.drive_distance_m,
        odometry_total_m=latest.odometry_total_m,
        note=latest.note,
        provenance=Provenance.REAL_OBSERVATION,
        source=_source(settings.mmgis_waypoints_url, latest.retrieved_at),
        caveats=CAVEATS,
    )


@router.get("/waypoints", response_model=schemas.WaypointList)
def waypoints(session: SessionDep, settings: SettingsDep) -> schemas.WaypointList:
    rows = _ordered(session)
    return schemas.WaypointList(
        items=[
            schemas.WaypointPoint(
                sol=w.sol,
                site=w.site,
                drive=w.drive,
                lat=w.lat,
                lon=w.lon,
                elevation_m=w.elevation_m,
                odometry_total_m=w.odometry_total_m,
            )
            for w in rows
        ],
        provenance=Provenance.REAL_OBSERVATION,
        source=_source(settings.mmgis_waypoints_url, rows[-1].retrieved_at if rows else None),
    )
