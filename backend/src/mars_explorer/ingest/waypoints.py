"""Real Perseverance localizations from the JPL MMGIS "Where is the rover" layer.

``M20_waypoints.json`` is a GeoJSON FeatureCollection of end-of-drive (and some mid-drive)
localizations. ``-9999`` marks missing values (seen in ``elev_radii``/``radius``).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from mars_explorer.core.errors import UpstreamError
from mars_explorer.ingest.parse import clean, to_float, to_int

MISSING_SENTINEL = -9999.0


class WaypointIn(BaseModel):
    source_index: int
    sol: int
    site: int | None
    drive: int | None
    lat: float
    lon: float
    elevation_m: float | None
    easting: float | None
    northing: float | None
    roll_deg: float | None
    pitch_deg: float | None
    yaw_deg: float | None
    tilt_deg: float | None
    drive_distance_m: float | None
    odometry_total_m: float | None
    note: str | None
    final: bool | None


def _value(raw: Any) -> float | None:
    number = to_float(raw)
    if number is None or number <= MISSING_SENTINEL:
        return None
    return number


def parse_waypoints(geojson: Any) -> list[WaypointIn]:
    if not isinstance(geojson, dict) or not isinstance(geojson.get("features"), list):
        raise UpstreamError("MMGIS waypoints payload is not a GeoJSON FeatureCollection")
    waypoints: list[WaypointIn] = []
    for index, feature in enumerate(geojson["features"]):
        props = (feature or {}).get("properties") or {}
        sol = to_int(props.get("sol"))
        lat, lon = _value(props.get("lat")), _value(props.get("lon"))
        if sol is None or lat is None or lon is None:
            continue  # unusable localization; never invent a position
        final = clean(props.get("final"))
        odometry = _value(props.get("dist_total_m"))
        drive_distance = _value(props.get("dist_m"))
        if waypoints and odometry == 0.0:
            # Mid-drive fixes carry dist_total_m = 0.0 (verified 2026-11-16): a cumulative
            # odometry cannot return to zero after the first fix, so it means "not provided".
            odometry = None
            drive_distance = None if drive_distance == 0.0 else drive_distance
        waypoints.append(
            WaypointIn(
                source_index=index,
                sol=sol,
                site=to_int(props.get("site")),
                drive=to_int(props.get("drive")),
                lat=lat,
                lon=lon,
                elevation_m=_value(props.get("elev_geoid")),
                easting=_value(props.get("easting")),
                northing=_value(props.get("northing")),
                roll_deg=_value(props.get("roll")),
                pitch_deg=_value(props.get("pitch")),
                yaw_deg=_value(props.get("yaw")),
                tilt_deg=_value(props.get("tilt")),
                drive_distance_m=drive_distance,
                odometry_total_m=odometry,
                note=clean(props.get("Note")),
                final=None if final is None else str(final).lower() in {"y", "yes", "true"},
            )
        )
    return waypoints
