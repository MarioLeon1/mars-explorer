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


# ---- Contract v1.2 (Phase 3: Perception) -----------------------------------------------------


class ParamSpecOut(ApiModel):
    name: str
    label: str
    type: Literal["int", "float", "bool", "choice"]
    default: int | float | bool | str
    help: str
    min: float | None
    max: float | None
    step: float | None
    choices: list[str]


class VisionMethod(ApiModel):
    name: str
    title: str
    category: str
    kind: Literal["algorithmic"]
    summary: str
    params: list[ParamSpecOut]
    limitations: list[str]
    score_definition: str | None
    experimental: bool
    produces_detections: bool


class AnalysisRequest(BaseModel):
    image_id: str
    method: str
    params: dict[str, Any] = Field(default_factory=dict)
    rendition: Literal["large", "full_res"] = "large"


class Detection(ApiModel):
    x: float
    y: float
    r: float
    score: float
    area_px: float


class LayerOut(ApiModel):
    name: str
    label: str
    url: str


class VisionAnalysisOut(ApiModel):
    id: str
    image_id: str
    method: str
    title: str
    method_kind: Literal["algorithmic"]
    provenance: Provenance
    rendition: str
    params: dict[str, Any]
    algorithm_version: str
    width: int
    height: int
    timings_ms: dict[str, float]
    stats: dict[str, Any]
    detections: list[Detection] | None
    layers: list[LayerOut]
    score_definition: str | None
    limitations: list[str]
    created_at: UtcDateTime


class AnnotationIn(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    label: Literal["rock"] = "rock"


class AnnotationOut(ApiModel):
    id: int
    image_id: str
    x: float
    y: float
    label: str
    provenance: Provenance
    created_at: UtcDateTime


class EvaluationOut(ApiModel):
    analysis_id: str
    annotations: int
    detections: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1: float | None
    tolerance_px: float
    matching: str
    caveats: list[str]


class MatchRequest(BaseModel):
    image_a: str
    image_b: str
    rendition: Literal["large", "full_res"] = "large"


class DrawnMatch(ApiModel):
    ax: float
    ay: float
    bx: float
    by: float
    inlier: bool


class MatchOut(ApiModel):
    image_a: str
    image_b: str
    stereo_pair: bool
    width_a: int
    height_a: int
    width_b: int
    height_b: int
    keypoints_a: int
    keypoints_b: int
    tentative: int
    inliers: int
    inlier_ratio: float | None
    disparity: dict[str, float]
    matches: list[DrawnMatch]
    elapsed_ms: float
    provenance: Provenance
    notes: list[str]


class BenchmarkRequest(BaseModel):
    cameras: list[str] = Field(default_factory=list, max_length=12)
    limit: int = Field(default=30, ge=1, le=80)


class Summary(ApiModel):
    mean: float
    median: float
    p95: float


class MethodBenchmarkOut(ApiModel):
    method: str
    title: str
    images: int
    runtime_ms: Summary | None
    candidates: Summary | None
    annotated_images: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    f1: float | None


class BenchmarkOut(ApiModel):
    images: int
    cameras: list[str]
    methods: list[MethodBenchmarkOut]
    agreement_f1: Summary | None
    notes: list[str]


# ---- Contract v1.3 (Phase 4: Terrain & Navigation) ---------------------------------------------


class EN(BaseModel):
    """A point in the PLACES DEM projection (metres): easting, northing."""

    e: float
    n: float


class CostModelIn(BaseModel):
    max_slope_deg: float = Field(default=30.0, ge=5, le=45)
    slope_weight: float = Field(default=4.0, ge=0, le=20)
    max_roughness_m: float = Field(default=0.30, ge=0.05, le=2.0)
    roughness_weight: float = Field(default=3.0, ge=0, le=20)


class MapRequest(BaseModel):
    center: EN | None = None
    size_m: float = Field(default=800, ge=100, le=3000)
    drives: tuple[int, int] | None = None  # (first, last) drive indices; overrides center/size
    margin_m: float = Field(default=120, ge=20, le=500)
    cost_model: CostModelIn = Field(default_factory=CostModelIn)


class LegendItem(ApiModel):
    label: str
    color: str


class TerrainLayer(ApiModel):
    name: str
    label: str
    url: str
    legend: list[LegendItem]


class Extent(ApiModel):
    e_min: float
    e_max: float
    n_min: float
    n_max: float


class DrivePath(ApiModel):
    index: int
    sol: int
    from_rmc: str | None
    to_rmc: str | None
    length_m: float | None
    points: list[list[float]]


class TerrainMapOut(ApiModel):
    id: str
    center: EN
    size_m: int
    cell_m: int
    grid: list[int]
    extent: Extent
    cost_model: dict[str, float]
    layers: list[TerrainLayer]
    stats: dict[str, Any]
    drives_in_view: list[DrivePath]
    provenance: Provenance
    assumptions: list[str]
    limitations: list[str]


class PlanRequest(BaseModel):
    map: MapRequest
    start: EN | None = None
    goal: EN | None = None
    planners: list[str] = Field(
        default_factory=lambda: ["astar", "dijkstra", "theta_star", "rrt_star"]
    )
    rrt_seed: int = Field(default=42, ge=0, le=2**31 - 1)
    rrt_iterations: int = Field(default=3000, ge=200, le=10000)


class RouteMetricsOut(ApiModel):
    feasible: bool
    length_m: float
    impassable_m: float
    cost: float | None
    cost_distance: float
    cost_slope: float
    cost_roughness: float
    max_slope_deg: float
    mean_slope_deg: float
    max_roughness_m: float
    elevation_gain_m: float
    elevation_loss_m: float
    min_clearance_m: float | None
    profile: list[list[float]]


class RouteOut(ApiModel):
    planner: str
    title: str
    kind: Literal["deterministic", "randomized", "real_observation"]
    found: bool
    reason: str | None
    points: list[list[float]]
    metrics: RouteMetricsOut | None
    expanded: int
    elapsed_ms: float
    extra: dict[str, float | int]


class PlanOut(ApiModel):
    map: TerrainMapOut
    start: EN
    goal: EN
    snapped: bool
    routes: list[RouteOut]
    actual: RouteOut | None
    best: str | None
    explanation: list[str]
    provenance: Provenance


# ---- Contract v1.4 (Phase 5: Mission Replay + AI assistant) ----------------------------------

SequenceKindOut = Literal[
    "fixed_pointing", "pointing_sweep", "vehicle_fixed", "single_exposure", "unclassified"
]


class SequenceSummary(ApiModel):
    id: str
    sol: int
    camera: Camera
    sequence_id: str | None
    kind: SequenceKindOut
    kind_note: str
    frame_count: int
    duration_s: float | None
    median_interval_s: float | None
    distinct_pointings: int | None
    start_lmst: str | None
    thumb_url: str
    label: Literal["reconstructed"] = "reconstructed"
    provenance: Provenance  # derived: the grouping/ordering is ours; each frame is real


class SequenceFrame(ApiModel):
    image_id: str
    t_offset_s: float | None
    sclk: float | None
    lmst: str | None
    width: int | None
    height: int | None
    thumb_url: str
    preview_url: str
    provenance: Provenance


class SequenceDetail(SequenceSummary):
    frames: list[SequenceFrame]
    notes: list[str]
    credits: list[str]
    real_time_available: bool


class SolActivityOut(ApiModel):
    sol: int
    images: int
    sequences: int
    drives: int
    drive_m: float


class MissionTimeline(ApiModel):
    sols: list[SolActivityOut]
    total_drive_m: float
    drive_sols: int
    image_sols: int
    provenance: Provenance
    sources: list[SourceRef]
    notes: list[str]


class TimelineImageOut(ApiModel):
    image_id: str
    camera: Camera
    lmst: str | None
    lmst_h: float | None
    sclk: float | None
    sequence_id: str | None
    thumb_url: str


class TimelineDriveOut(ApiModel):
    index: int
    from_rmc: str | None
    to_rmc: str | None
    length_m: float | None
    start_lmst_h: float | None
    end_lmst_h: float | None
    provenance: Provenance  # the drive is real; its LMST placement is derived


class LmstCalibrationOut(ApiModel):
    samples: int
    max_residual_s: float
    method: str


class SolTimelineOut(ApiModel):
    sol: int
    images: list[TimelineImageOut]
    sequences: list[SequenceSummary]
    drives: list[TimelineDriveOut]
    end_of_sol_position: WaypointPoint | None
    lmst_calibration: LmstCalibrationOut | None
    previous_sol: int | None
    next_sol: int | None
    notes: list[str]


class FeaturedSequenceOut(ApiModel):
    key: str
    title: str
    description: str
    sol: int
    camera: Camera
    sequence_id: str
    published_frames: int
    local_frames: int
    sequence_url: str | None  # /api/replay/sequences/{id} once frames are stored
    job_request: IngestJobRequest
    provenance: Provenance


class OfficialVideoOut(ApiModel):
    nasa_id: str
    title: str
    date: str
    sol: int | None
    description: str
    credit: str
    video_url: str
    poster_url: str
    page_url: str
    label: Literal["official_nasa_video"] = "official_nasa_video"
    provenance: Provenance


class AssistantToolOut(ApiModel):
    name: str
    description: str


class ModelPrice(ApiModel):
    model: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    note: str


class AssistantStatusOut(ApiModel):
    enabled: bool
    model: str
    effort: str
    fallbacks: bool
    max_tool_rounds: int
    tools: list[AssistantToolOut]
    how_to_enable: list[str]
    data_sent: list[str]
    never: list[str]
    pricing: list[ModelPrice]


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatContextIn(BaseModel):
    page: str | None = Field(default=None, max_length=40)
    sol: int | None = Field(default=None, ge=0)
    image_id: str | None = Field(default=None, max_length=80)


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=40)
    context: ChatContextIn | None = None


class ToolCallOut(ApiModel):
    name: str
    input: dict[str, Any]
    is_error: bool
    result_chars: int


class UsageOut(ApiModel):
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int


class ChatResponse(ApiModel):
    reply: str
    model: str
    stop_reason: str | None
    refused: bool
    fallback_used: bool
    rounds: int
    tool_calls: list[ToolCallOut]
    usage: UsageOut
    notes: list[str]
    label: Literal["ai_generated"] = "ai_generated"
    provenance: Provenance  # derived: model-written text over the app's data
