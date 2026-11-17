"""Database tables. All datetimes are timezone-aware UTC (enforced by SQLModel)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from mars_explorer.core.provenance import Provenance


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ImageRecord(SQLModel, table=True):
    """One Perseverance raw image, normalised, plus its original NASA record verbatim."""

    __tablename__ = "images"

    image_id: str = Field(primary_key=True)
    sol: int = Field(index=True)
    instrument: str = Field(index=True)
    camera_group: str = Field(index=True)
    sample_type: str
    date_taken_utc: datetime | None = Field(default=None, index=True)
    date_taken_mars: str | None = None
    lmst: str | None = None
    site: int | None = None
    drive: int | None = None
    width: int | None = None
    height: int | None = None
    title: str | None = None
    caption: str | None = Field(default=None, sa_column=Column(Text))
    credit: str | None = None
    date_received: datetime | None = None
    filter_name: str | None = None
    sequence_id: str | None = None
    mast_az: float | None = None
    mast_el: float | None = None
    sclk: float | None = None
    scale_factor: float | None = None
    subframe_rect: list[int] | None = Field(default=None, sa_column=Column(JSON))
    attitude_quaternion: list[float] | None = Field(default=None, sa_column=Column(JSON))
    camera_model_type: str | None = None
    camera_position: list[float] | None = Field(default=None, sa_column=Column(JSON))
    camera_vector: list[float] | None = Field(default=None, sa_column=Column(JSON))
    url_small: str | None = None
    url_medium: str | None = None
    url_large: str | None = None
    url_full_res: str | None = None
    nasa_page_url: str | None = None
    nasa_json_url: str | None = None
    raw_json: str = Field(sa_column=Column(Text, nullable=False))
    provenance: str = Provenance.REAL_OBSERVATION.value
    ingested_at: datetime = Field(default_factory=utcnow)

    def original_url(self, size: str) -> str | None:
        return {
            "small": self.url_small,
            "medium": self.url_medium,
            "large": self.url_large,
            "full_res": self.url_full_res,
        }.get(size)


class ImageFile(SQLModel, table=True):
    """A locally cached copy of one rendition of an image."""

    __tablename__ = "image_files"
    __table_args__ = (UniqueConstraint("image_id", "size"),)

    id: int | None = Field(default=None, primary_key=True)
    image_id: str = Field(index=True, foreign_key="images.image_id")
    size: str
    path: str  # relative to settings.data_dir, POSIX separators
    bytes: int
    sha256: str
    content_type: str
    source_url: str
    downloaded_at: datetime = Field(default_factory=utcnow)


class Waypoint(SQLModel, table=True):
    """A real rover localization published by JPL (MMGIS). Replaced wholesale on each refresh."""

    __tablename__ = "waypoints"

    id: int | None = Field(default=None, primary_key=True)
    source_index: int
    sol: int = Field(index=True)
    site: int | None = None
    drive: int | None = None
    lat: float
    lon: float
    elevation_m: float | None = None
    easting: float | None = None
    northing: float | None = None
    roll_deg: float | None = None
    pitch_deg: float | None = None
    yaw_deg: float | None = None
    tilt_deg: float | None = None
    drive_distance_m: float | None = None
    odometry_total_m: float | None = None
    note: str | None = None
    final: bool | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)


class IngestRun(SQLModel, table=True):
    __tablename__ = "ingest_runs"

    id: int | None = Field(default=None, primary_key=True)
    kind: str
    params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    status: str = "running"  # running | success | partial | failed
    items_seen: int = 0
    items_added: int = 0
    items_skipped: int = 0
    items_failed: int = 0
    files_downloaded: int = 0
    files_skipped: int = 0
    error: str | None = Field(default=None, sa_column=Column(Text))


class FeedStatus(SQLModel, table=True):
    """Last known state of the upstream raw-images feed (single row, id=1)."""

    __tablename__ = "feed_status"

    id: int = Field(default=1, primary_key=True)
    latest_sol: int | None = None
    total_images: int | None = None
    checked_at: datetime = Field(default_factory=utcnow)


class VisionAnalysis(SQLModel, table=True):
    """A cached perception result (derived data). Id = hash of inputs + algorithm version."""

    __tablename__ = "vision_analyses"

    id: str = Field(primary_key=True)
    image_id: str = Field(index=True, foreign_key="images.image_id")
    method: str = Field(index=True)
    rendition: str
    params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    algorithm_version: str
    width: int
    height: int
    timings_ms: dict[str, float] = Field(default_factory=dict, sa_column=Column(JSON))
    stats: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    detections: list[dict[str, float]] | None = Field(default=None, sa_column=Column(JSON))
    layers: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Annotation(SQLModel, table=True):
    """A point marked by the user on an image (user_generated). Coordinates are fractions of
    the image width/height so they are independent of the rendition."""

    __tablename__ = "annotations"

    id: int | None = Field(default=None, primary_key=True)
    image_id: str = Field(index=True, foreign_key="images.image_id")
    x: float
    y: float
    label: str = "rock"
    created_at: datetime = Field(default_factory=utcnow)


class TraverseSegment(SQLModel, table=True):
    """One real drive as published by JPL MMGIS (dense polyline, ~1 m vertex spacing).

    ``points`` are [easting, northing, elevation] in the PLACES DEM projection (metres)."""

    __tablename__ = "traverse_segments"

    id: int | None = Field(default=None, primary_key=True)
    source_index: int = Field(index=True)
    sol: int = Field(index=True)
    from_rmc: str | None = None
    to_rmc: str | None = None
    length_m: float | None = None
    sclk_start: float | None = None
    sclk_end: float | None = None
    points: list[list[float | None]] = Field(default_factory=list, sa_column=Column(JSON))
    retrieved_at: datetime = Field(default_factory=utcnow)
