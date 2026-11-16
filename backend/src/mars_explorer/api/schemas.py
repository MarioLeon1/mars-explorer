"""Response models — the single source of truth for contract v1 on the backend side."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, PlainSerializer

from mars_explorer.core.provenance import Provenance
from mars_explorer.db.models import as_utc

ImageSize = Literal["small", "large", "full_res"]


def _iso_z(value: datetime) -> str:
    stamp = as_utc(value)
    assert stamp is not None
    return stamp.isoformat().replace("+00:00", "Z")


UtcDateTime = Annotated[datetime, PlainSerializer(_iso_z, return_type=str, when_used="json")]
"""A datetime always serialised as UTC ISO-8601 with a trailing ``Z``."""


class ApiModel(BaseModel):
    pass


class Health(ApiModel):
    status: Literal["ok"] = "ok"
    version: str


class SourceRef(ApiModel):
    name: str
    url: str
    credit: str | None = None
    retrieved_at: UtcDateTime | None = None


class LandingSite(ApiModel):
    name: str
    region: str
    lat: float
    lon: float


class MissionInfo(ApiModel):
    mission: str
    rover: str
    launch_date: date
    landing_date: date
    landing_site: LandingSite
    summary: str
    provenance: Provenance
    sources: list[SourceRef]


class Camera(ApiModel):
    instrument: str
    group: str
    label: str


class CameraWithCount(Camera):
    image_count: int


class SolSummary(ApiModel):
    sol: int
    image_count: int
    instruments: list[str]
    earliest_utc: UtcDateTime | None
    latest_utc: UtcDateTime | None


class ImageSummary(ApiModel):
    image_id: str
    sol: int
    camera: Camera
    sample_type: str
    date_taken_utc: UtcDateTime | None
    date_taken_mars: str | None
    lmst: str | None
    site: int | None
    drive: int | None
    width: int | None
    height: int | None
    thumb_url: str
    preview_url: str
    credit: str | None
    provenance: Provenance


class ImagePage(ApiModel):
    items: list[ImageSummary]
    total: int
    limit: int
    offset: int


class OriginalFiles(ApiModel):
    small: str | None
    medium: str | None
    large: str | None
    full_res: str | None


class ImageSource(ApiModel):
    nasa_page_url: str | None
    nasa_json_url: str | None
    original_files: OriginalFiles


class LocalFiles(ApiModel):
    small: bool
    large: bool
    full_res: bool


class ImageDetail(ImageSummary):
    title: str | None
    caption: str | None
    date_received: UtcDateTime | None
    filter_name: str | None
    sequence_id: str | None
    mast_az: float | None
    mast_el: float | None
    sclk: float | None
    scale_factor: float | None
    subframe_rect: list[int] | None
    attitude_quaternion: list[float] | None
    camera_model_type: str | None
    camera_position: list[float] | None
    camera_vector: list[float] | None
    source: ImageSource
    local_files: LocalFiles
    ingested_at: UtcDateTime
    notes: list[str]


class RoverPosition(ApiModel):
    sol: int
    site: int | None
    drive: int | None
    lat: float
    lon: float
    elevation_m: float | None
    roll_deg: float | None
    pitch_deg: float | None
    yaw_deg: float | None
    tilt_deg: float | None
    drive_distance_m: float | None
    odometry_total_m: float | None
    note: str | None
    provenance: Provenance
    source: SourceRef
    caveats: list[str]


class WaypointPoint(ApiModel):
    sol: int
    site: int | None
    drive: int | None
    lat: float
    lon: float
    elevation_m: float | None
    odometry_total_m: float | None


class WaypointList(ApiModel):
    items: list[WaypointPoint]
    provenance: Provenance
    source: SourceRef


class DatabaseCounts(ApiModel):
    images: int
    sols: int
    waypoints: int


class StorageStats(ApiModel):
    image_files: int
    bytes: int


class LastIngest(ApiModel):
    kind: str
    status: str
    finished_at: UtcDateTime | None
    items_added: int
    items_skipped: int
    items_failed: int


class FeedState(ApiModel):
    latest_sol: int | None
    total_images: int | None
    checked_at: UtcDateTime


class SystemStatus(ApiModel):
    api: Literal["ok"] = "ok"
    database: DatabaseCounts
    storage: StorageStats
    last_ingest: LastIngest | None
    feed: FeedState | None


# ---- Contract v1.1 (Phase 2: Explorer) ------------------------------------------------------


class Neighbors(ApiModel):
    previous: ImageSummary | None
    next: ImageSummary | None
    position: int | None  # 1-based position in chronological order within the filter
    total: int


class StereoInfo(ApiModel):
    partner_instrument: str
    candidate_id: str
    local: ImageSummary | None


class RelatedImages(ApiModel):
    same_sequence: list[ImageSummary]
    stereo: StereoInfo | None
    same_sol_other_cameras: list[ImageSummary]


class RawRecord(ApiModel):
    image_id: str
    provenance: Provenance
    source_url: str | None
    record: dict[str, Any]


class FeedAvailability(ApiModel):
    sol_min: int
    sol_max: int
    cameras: list[str]
    published: int | None
    stored: int
    checked_at: UtcDateTime
    source: SourceRef


class IngestJobRequest(BaseModel):
    sol_min: int = Field(ge=0)
    sol_max: int | None = Field(default=None, ge=0)
    cameras: list[str] = Field(default_factory=list, max_length=12)
    limit: int = Field(default=50, ge=1, le=200)
    full_res: bool = False


class JobProgress(ApiModel):
    seen: int
    added: int
    skipped: int
    failed: int
    downloaded: int


class IngestJob(ApiModel):
    id: str
    status: Literal["queued", "running", "success", "partial", "failed", "cancelled"]
    sol_min: int
    sol_max: int
    cameras: list[str]
    limit: int
    full_res: bool
    progress: JobProgress
    run_id: int | None
    error: str | None
    created_at: UtcDateTime
    started_at: UtcDateTime | None
    finished_at: UtcDateTime | None
