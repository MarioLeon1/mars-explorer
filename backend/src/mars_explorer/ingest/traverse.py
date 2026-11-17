"""Real Perseverance drive paths from the JPL MMGIS ``M20_traverse.json`` layer.

GeoJSON LineStrings in CRS84 (lon, lat, elevation), one per drive, ~1 m vertex spacing
(verified 2026-11-17: 559 drives, 36 661 vertices). Converted to the PLACES DEM projection.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from mars_explorer.core.errors import UpstreamError
from mars_explorer.ingest.parse import clean, to_float, to_int
from mars_explorer.terrain.dem import lonlat_to_en


class TraverseIn(BaseModel):
    source_index: int
    sol: int
    from_rmc: str | None
    to_rmc: str | None
    length_m: float | None
    sclk_start: float | None
    sclk_end: float | None
    points: list[list[float | None]]  # [easting, northing, elevation | None]


def parse_traverse(geojson: Any) -> list[TraverseIn]:
    if not isinstance(geojson, dict) or not isinstance(geojson.get("features"), list):
        raise UpstreamError("MMGIS traverse payload is not a GeoJSON FeatureCollection")
    drives: list[TraverseIn] = []
    for index, feature in enumerate(geojson["features"]):
        props = (feature or {}).get("properties") or {}
        geometry = (feature or {}).get("geometry") or {}
        sol = to_int(props.get("sol"))
        coords = geometry.get("coordinates") if geometry.get("type") == "LineString" else None
        if sol is None or not isinstance(coords, list) or len(coords) < 2:
            continue  # unusable drive; never invent geometry
        points: list[list[float | None]] = []
        for vertex in coords:
            lon, lat = to_float(vertex[0]), to_float(vertex[1])
            if lon is None or lat is None:
                continue
            easting, northing = lonlat_to_en(lon, lat)
            elevation = to_float(vertex[2]) if len(vertex) > 2 else None
            z = round(elevation, 2) if elevation is not None and elevation > -9999 else None
            points.append([round(easting, 2), round(northing, 2), z])
        if len(points) < 2:
            continue
        drives.append(
            TraverseIn(
                source_index=index,
                sol=sol,
                from_rmc=clean(props.get("fromRMC")),
                to_rmc=clean(props.get("toRMC")),
                length_m=to_float(props.get("length")),
                sclk_start=to_float(props.get("SCLK_START")),
                sclk_end=to_float(props.get("SCLK_END")),
                points=points,
            )
        )
    return drives
