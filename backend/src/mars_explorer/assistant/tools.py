"""Read-only tools the assistant may call. Every tool returns JSON built from this app's data.

Design rules:
* no tool writes to the database, downloads anything, or calls a planner (rule 6: the language
  model never controls navigation; route planning stays deterministic and user-initiated);
* every result names its provenance so the model can tell real observations from derived data;
* results are capped (``MAX_RESULT_CHARS``) to keep requests small and predictable.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from mars_explorer.core.provenance import Provenance
from mars_explorer.db.models import (
    Annotation,
    FeedStatus,
    ImageRecord,
    TraverseSegment,
    VisionAnalysis,
    Waypoint,
)
from mars_explorer.ingest.cameras import CATALOG, camera_info
from mars_explorer.replay.sequences import KIND_NOTES
from mars_explorer.replay.service import list_sequences, mission_activity, sol_timeline
from mars_explorer.terrain.service import TerrainService

MAX_RESULT_CHARS = 12_000
MAX_IMAGES = 25
MAX_DRIVES = 60

REAL = Provenance.REAL_OBSERVATION.value
DERIVED = Provenance.DERIVED.value


class ToolInputError(ValueError):
    """The model sent arguments the tool cannot use (reported back as ``is_error``)."""


@dataclass(frozen=True, slots=True)
class ToolContext:
    session: Session
    terrain: TerrainService | None


ToolFn = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    run: ToolFn

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


# ---- argument helpers ----------------------------------------------------------------------


def _int(
    args: dict[str, Any], key: str, *, low: int, high: int, default: int | None = None
) -> int | None:
    value = args.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ToolInputError(f"{key} must be an integer")
    try:
        number = int(value)
    except ValueError as exc:
        raise ToolInputError(f"{key} must be an integer") from exc
    if not low <= number <= high:
        raise ToolInputError(f"{key} must be between {low} and {high}")
    return number


def _str(args: dict[str, Any], key: str, *, max_len: int = 120) -> str | None:
    value = args.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > max_len:
        raise ToolInputError(f"{key} must be a string of at most {max_len} characters")
    return value.strip()


def _image_brief(image: ImageRecord) -> dict[str, Any]:
    return {
        "image_id": image.image_id,
        "sol": image.sol,
        "camera": image.instrument,
        "camera_label": camera_info(image.instrument).label,
        "lmst": image.lmst,
        "sequence_id": image.sequence_id,
        "size": [image.width, image.height],
        "credit": image.credit,
        "app_link": f"/explorer/{image.image_id}",
    }


def _schema(properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties or {}, "additionalProperties": False}


# ---- tools ---------------------------------------------------------------------------------


def mission_overview(ctx: ToolContext, _: dict[str, Any]) -> dict[str, Any]:
    session = ctx.session
    images = session.exec(select(func.count()).select_from(ImageRecord)).one()
    sols = [
        row
        for row in session.exec(
            select(ImageRecord.sol).distinct().order_by(ImageRecord.sol)  # type: ignore[arg-type]
        ).all()
    ]
    feed = session.get(FeedStatus, 1)
    activity = mission_activity(session)
    latest = session.exec(
        select(Waypoint).order_by(Waypoint.sol.desc(), Waypoint.source_index.desc())  # type: ignore[attr-defined]
    ).first()
    return {
        "mission": "Mars 2020 — Perseverance rover, landed 2021-02-18 at Octavia E. Butler "
        "Landing, Jezero crater (18.4447 N, 77.4508 E).",
        "stored_images": images,
        "sols_with_stored_images": sols,
        "real_drives": {
            "count": sum(a.drives for a in activity),
            "total_length_m": round(sum(a.drive_m for a in activity), 1),
            "sols_with_drives": sum(1 for a in activity if a.drives),
            "provenance": REAL,
        },
        "latest_localization_sol": latest.sol if latest else None,
        "upstream_feed": (
            {"latest_sol": feed.latest_sol, "total_images": feed.total_images}
            if feed
            else "never checked"
        ),
        "note": "Stored images are a local subset; NASA has published far more.",
    }


def rover_position(ctx: ToolContext, _: dict[str, Any]) -> dict[str, Any]:
    latest = ctx.session.exec(
        select(Waypoint).order_by(Waypoint.sol.desc(), Waypoint.source_index.desc())  # type: ignore[attr-defined]
    ).first()
    if latest is None:
        return {"available": False, "reason": "No localizations ingested."}
    return {
        "available": True,
        "sol": latest.sol,
        "site": latest.site,
        "drive": latest.drive,
        "lat": latest.lat,
        "lon": latest.lon,
        "elevation_m": latest.elevation_m,
        "odometry_total_m": latest.odometry_total_m,
        "provenance": REAL,
        "source": "JPL MMGIS M20_waypoints.json",
        "caveats": [
            "Localizations are published with a delay.",
            "Elevation is relative to the Mars areoid.",
            "There is no public real-time telemetry (battery, power, health).",
        ],
    }


def search_images(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sol = _int(args, "sol", low=0, high=100_000)
    camera = _str(args, "camera", max_len=40)
    limit = _int(args, "limit", low=1, high=MAX_IMAGES, default=10)
    assert limit is not None
    query = select(ImageRecord)
    if sol is not None:
        query = query.where(ImageRecord.sol == sol)
    if camera:
        if camera not in CATALOG:
            raise ToolInputError(f"unknown camera {camera!r}; valid: {', '.join(CATALOG)}")
        query = query.where(ImageRecord.instrument == camera)
    total = ctx.session.exec(select(func.count()).select_from(query.subquery())).one()
    rows = ctx.session.exec(
        query.order_by(ImageRecord.sol.desc(), ImageRecord.sclk).limit(limit)  # type: ignore[union-attr]
    ).all()
    return {
        "total_matching": total,
        "returned": len(rows),
        "images": [_image_brief(r) for r in rows],
        "provenance": REAL,
    }


def image_details(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    image_id = _str(args, "image_id", max_len=80)
    if not image_id:
        raise ToolInputError("image_id is required")
    image = ctx.session.get(ImageRecord, image_id)
    if image is None:
        return {"found": False, "image_id": image_id, "note": "Not in the local archive."}
    analyses = ctx.session.exec(
        select(VisionAnalysis).where(VisionAnalysis.image_id == image_id)
    ).all()
    annotations = ctx.session.exec(
        select(func.count()).where(Annotation.image_id == image_id)
    ).one()
    return {
        "found": True,
        **_image_brief(image),
        "title": image.title,
        "caption": (image.caption or "")[:1500],
        "date_taken_utc": image.date_taken_utc.isoformat() if image.date_taken_utc else None,
        "sclk": image.sclk,
        "site": image.site,
        "drive": image.drive,
        "mast_az_deg": image.mast_az,
        "mast_el_deg": image.mast_el,
        "filter": image.filter_name,
        "nasa_page": image.nasa_page_url,
        "provenance": REAL,
        "product_note": "Raw, uncalibrated browse product: no physical measurements from it.",
        "perception_results": [
            {
                "method": a.method,
                "detections": len(a.detections or []),
                "stats": a.stats,
                "provenance": DERIVED,
                "nature": "algorithmic candidates, not confirmed rocks",
            }
            for a in analyses
        ],
        "user_annotations": annotations,
    }


def drives(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sol_min = _int(args, "sol_min", low=0, high=100_000, default=0)
    sol_max = _int(args, "sol_max", low=0, high=100_000, default=100_000)
    assert sol_min is not None and sol_max is not None
    if sol_max < sol_min:
        raise ToolInputError("sol_max must be >= sol_min")
    rows = ctx.session.exec(
        select(TraverseSegment)
        .where(TraverseSegment.sol >= sol_min, TraverseSegment.sol <= sol_max)
        .order_by(TraverseSegment.source_index)  # type: ignore[arg-type]
    ).all()
    lengths = [r.length_m or 0.0 for r in rows]
    return {
        "count": len(rows),
        "total_length_m": round(sum(lengths), 1),
        "longest_m": round(max(lengths), 1) if lengths else None,
        "drives": [
            {
                "index": r.source_index,
                "sol": r.sol,
                "length_m": r.length_m,
                "from": r.from_rmc,
                "to": r.to_rmc,
            }
            for r in rows[:MAX_DRIVES]
        ],
        "truncated": len(rows) > MAX_DRIVES,
        "provenance": REAL,
        "source": "JPL MMGIS M20_traverse.json",
    }


def sol_summary(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sol = _int(args, "sol", low=0, high=100_000)
    if sol is None:
        raise ToolInputError("sol is required")
    timeline = sol_timeline(ctx.session, sol)
    if timeline is None:
        return {"sol": sol, "found": False, "note": "No stored images or real drives that sol."}
    cameras: dict[str, int] = {}
    for item in timeline.images:
        cameras[item.image.instrument] = cameras.get(item.image.instrument, 0) + 1
    lmsts = [t.lmst_h for t in timeline.images if t.lmst_h is not None]
    return {
        "sol": sol,
        "found": True,
        "images_by_camera": cameras,
        "imaging_window_lmst_h": [round(min(lmsts), 2), round(max(lmsts), 2)] if lmsts else None,
        "sequences": [
            {"id": s.id, "camera": s.instrument, "frames": s.frame_count, "kind": s.kind}
            for s in timeline.sequences
        ],
        "drives": [
            {
                "length_m": d.segment.length_m,
                "start_lmst_h": d.start_lmst_h,
                "end_lmst_h": d.end_lmst_h,
                "time_placement": "derived from SCLK, calibrated on this sol's images",
            }
            for d in timeline.drives
        ],
        "end_of_sol_localization": (
            {
                "lat": timeline.end_of_sol_waypoint.lat,
                "lon": timeline.end_of_sol_waypoint.lon,
                "elevation_m": timeline.end_of_sol_waypoint.elevation_m,
            }
            if timeline.end_of_sol_waypoint
            else None
        ),
        "app_link": f"/replay?sol={sol}",
    }


def sequences(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    sol = _int(args, "sol", low=0, high=100_000)
    found = list_sequences(ctx.session, sol, min_frames=3)
    return {
        "count": len(found),
        "sequences": [
            {
                "id": s.id,
                "sol": s.sol,
                "camera": s.instrument,
                "frames": s.frame_count,
                "duration_s": round(s.duration_s, 1) if s.duration_s is not None else None,
                "kind": s.kind,
            }
            for s in found[:40]
        ],
        "kinds": KIND_NOTES,
        "label": "reconstructed from raw frames, never a NASA video",
        "provenance": DERIVED,
    }


def terrain_status(ctx: ToolContext, _: dict[str, Any]) -> dict[str, Any]:
    if ctx.terrain is None:
        return {"available": False}
    status = ctx.terrain.status()
    status.pop("how_to_get", None)
    return {
        **status,
        "planning_note": (
            "Route planning is deterministic (A*, Dijkstra, Theta*) or seeded (RRT*) and runs only "
            "when the user asks in the Terrain page. The assistant cannot plan or change routes."
        ),
    }


TOOLS: tuple[Tool, ...] = (
    Tool(
        "get_mission_overview",
        "Overview of what this app holds: stored image count and sols, real drive totals, latest "
        "localization sol and the last known state of NASA's raw-image feed. Call first for broad "
        "questions.",
        _schema(),
        mission_overview,
    ),
    Tool(
        "get_rover_position",
        "Latest real rover localization published by JPL (sol, lat/lon, elevation, odometry) "
        "with caveats. There is no real-time telemetry.",
        _schema(),
        rover_position,
    ),
    Tool(
        "search_images",
        "List stored raw images, optionally filtered by sol and camera instrument id (e.g. "
        "NAVCAM_LEFT, MCZ_LEFT, FRONT_HAZCAM_LEFT_A). Returns ids, LMST, sequence ids, credits.",
        _schema(
            {
                "sol": {"type": "integer", "minimum": 0, "description": "Mission sol"},
                "camera": {"type": "string", "description": "Instrument id"},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_IMAGES},
            }
        ),
        search_images,
    ),
    Tool(
        "get_image_details",
        "Full metadata of one stored image: NASA caption, pointing, time, credit, perception "
        "results computed in this app and the number of user annotations.",
        {**_schema({"image_id": {"type": "string"}}), "required": ["image_id"]},
        image_details,
    ),
    Tool(
        "get_drives",
        "Real drives published by JPL (MMGIS traverse) between two sols: count, lengths, RMC "
        "start/end labels.",
        _schema(
            {
                "sol_min": {"type": "integer", "minimum": 0},
                "sol_max": {"type": "integer", "minimum": 0},
            }
        ),
        drives,
    ),
    Tool(
        "get_sol_summary",
        "What happened on one sol according to stored data: images per camera, imaging window in "
        "local solar time, reconstructed sequences, real drives with derived time placement, and "
        "the end-of-sol localization.",
        {**_schema({"sol": {"type": "integer", "minimum": 0}}), "required": ["sol"]},
        sol_summary,
    ),
    Tool(
        "list_sequences",
        "Frame sequences reconstructed from stored raw images (3+ frames), optionally for one "
        "sol, with their kind (fixed pointing, pointing sweep, vehicle-fixed, single exposure).",
        _schema({"sol": {"type": "integer", "minimum": 0}}),
        sequences,
    ),
    Tool(
        "get_terrain_status",
        "Status of the 1 m orbital elevation model (PDS PLACES) used for terrain analysis: "
        "availability, extent, and validation against real localizations.",
        _schema(),
        terrain_status,
    ),
)

TOOLS_BY_NAME: dict[str, Tool] = {t.name: t for t in TOOLS}


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> tuple[str, bool]:
    """Execute a tool. Returns ``(json_text, is_error)``; never raises for bad model input."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return json.dumps({"error": f"unknown tool {name!r}"}), True
    try:
        result = tool.run(ctx, args if isinstance(args, dict) else {})
    except ToolInputError as exc:
        return json.dumps({"error": str(exc)}), True
    text = json.dumps(result, default=str, ensure_ascii=False, sort_keys=True)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + " ... [truncated]"
    return text, False
