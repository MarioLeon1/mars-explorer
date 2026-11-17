// Mirrors docs/api/contract-v1.md. Keep in sync with backend/src/mars_explorer/api/schemas.py.

export type Provenance = 'real_observation' | 'derived' | 'simulated' | 'user_generated'

export type CameraGroup =
  | 'navcam'
  | 'hazcam_front'
  | 'hazcam_rear'
  | 'mastcamz'
  | 'skycam'
  | 'supercam'
  | 'sherloc'
  | 'pixl'
  | 'cachecam'
  | 'edl'
  | 'helicopter'
  | 'other'

export type ImageSize = 'small' | 'large' | 'full_res'

/** ISO-8601 UTC timestamp with trailing Z. */
export type IsoUtc = string

export interface SourceRef {
  name: string
  url: string
  credit: string | null
  retrieved_at: IsoUtc | null
}

export interface Camera {
  instrument: string
  group: CameraGroup
  label: string
}

export interface CameraWithCount extends Camera {
  image_count: number
}

export interface Health {
  status: 'ok'
  version: string
}

export interface MissionInfo {
  mission: string
  rover: string
  launch_date: string
  landing_date: string
  landing_site: { name: string; region: string; lat: number; lon: number }
  summary: string
  provenance: Provenance
  sources: SourceRef[]
}

export interface SolSummary {
  sol: number
  image_count: number
  instruments: string[]
  earliest_utc: IsoUtc | null
  latest_utc: IsoUtc | null
}

export interface ImageSummary {
  image_id: string
  sol: number
  camera: Camera
  sample_type: string
  date_taken_utc: IsoUtc | null
  date_taken_mars: string | null
  lmst: string | null
  site: number | null
  drive: number | null
  width: number | null
  height: number | null
  thumb_url: string
  preview_url: string
  credit: string | null
  provenance: Provenance
}

export interface ImagePage {
  items: ImageSummary[]
  total: number
  limit: number
  offset: number
}

export interface ImageDetail extends ImageSummary {
  title: string | null
  caption: string | null
  date_received: IsoUtc | null
  filter_name: string | null
  sequence_id: string | null
  mast_az: number | null
  mast_el: number | null
  sclk: number | null
  scale_factor: number | null
  subframe_rect: number[] | null
  attitude_quaternion: number[] | null
  camera_model_type: string | null
  camera_position: number[] | null
  camera_vector: number[] | null
  source: {
    nasa_page_url: string | null
    nasa_json_url: string | null
    original_files: Record<'small' | 'medium' | 'large' | 'full_res', string | null>
  }
  local_files: Record<ImageSize, boolean>
  ingested_at: IsoUtc
  notes: string[]
}

export interface RoverPosition {
  sol: number
  site: number | null
  drive: number | null
  lat: number
  lon: number
  elevation_m: number | null
  roll_deg: number | null
  pitch_deg: number | null
  yaw_deg: number | null
  tilt_deg: number | null
  drive_distance_m: number | null
  odometry_total_m: number | null
  note: string | null
  provenance: Provenance
  source: SourceRef
  caveats: string[]
}

export interface WaypointPoint {
  sol: number
  site: number | null
  drive: number | null
  lat: number
  lon: number
  elevation_m: number | null
  odometry_total_m: number | null
}

export interface WaypointList {
  items: WaypointPoint[]
  provenance: Provenance
  source: SourceRef
}

export interface SystemStatus {
  api: 'ok'
  database: { images: number; sols: number; waypoints: number }
  storage: { image_files: number; bytes: number }
  last_ingest: {
    kind: string
    status: 'success' | 'partial' | 'failed' | 'running'
    finished_at: IsoUtc | null
    items_added: number
    items_skipped: number
    items_failed: number
  } | null
  feed: { latest_sol: number | null; total_images: number | null; checked_at: IsoUtc } | null
}

export interface ApiErrorBody {
  error: { code: string; message: string }
}

// ---- Contract v1.1 (Phase 2: Explorer) ---------------------------------------------------

export interface Neighbors {
  previous: ImageSummary | null
  next: ImageSummary | null
  /** 1-based chronological position within the filter; null if the image is outside it */
  position: number | null
  total: number
}

export interface StereoInfo {
  partner_instrument: string
  /** The id the other eye would have — unverified until `local` is set or NASA confirms it */
  candidate_id: string
  local: ImageSummary | null
}

export interface RelatedImages {
  same_sequence: ImageSummary[]
  stereo: StereoInfo | null
  same_sol_other_cameras: ImageSummary[]
}

export interface RawRecord {
  image_id: string
  provenance: Provenance
  source_url: string | null
  record: Record<string, unknown>
}

export interface FeedAvailability {
  sol_min: number
  sol_max: number
  cameras: string[]
  published: number | null
  stored: number
  checked_at: IsoUtc
  source: SourceRef
}

export type JobStatus = 'queued' | 'running' | 'success' | 'partial' | 'failed' | 'cancelled'

export interface IngestJob {
  id: string
  status: JobStatus
  sol_min: number
  sol_max: number
  cameras: string[]
  limit: number
  full_res: boolean
  progress: { seen: number; added: number; skipped: number; failed: number; downloaded: number }
  run_id: number | null
  error: string | null
  created_at: IsoUtc
  started_at: IsoUtc | null
  finished_at: IsoUtc | null
}

export interface IngestJobRequest {
  sol_min: number
  sol_max?: number
  cameras: string[]
  limit: number
  full_res: boolean
}

// ---- Contract v1.2 (Phase 3: Perception) ---------------------------------------------------

export type ParamValue = number | boolean | string

export interface ParamSpec {
  name: string
  label: string
  type: 'int' | 'float' | 'bool' | 'choice'
  default: ParamValue
  help: string
  min: number | null
  max: number | null
  step: number | null
  choices: string[]
}

export interface VisionMethod {
  name: string
  title: string
  category: 'enhancement' | 'structure' | 'detection' | 'segmentation' | 'features'
  kind: 'algorithmic'
  summary: string
  params: ParamSpec[]
  limitations: string[]
  score_definition: string | null
  experimental: boolean
  produces_detections: boolean
}

export interface Detection {
  /** centre and radius in pixels of the analysed rendition */
  x: number
  y: number
  r: number
  score: number
  area_px: number
}

export interface VisionAnalysis {
  id: string
  image_id: string
  method: string
  title: string
  method_kind: 'algorithmic'
  provenance: Provenance
  rendition: string
  params: Record<string, ParamValue>
  algorithm_version: string
  width: number
  height: number
  timings_ms: Record<string, number>
  stats: Record<string, number | string>
  detections: Detection[] | null
  layers: { name: string; label: string; url: string }[]
  score_definition: string | null
  limitations: string[]
  created_at: IsoUtc
}

export interface Annotation {
  id: number
  image_id: string
  /** fractions of image width / height */
  x: number
  y: number
  label: string
  provenance: Provenance
  created_at: IsoUtc
}

export interface Evaluation {
  analysis_id: string
  annotations: number
  detections: number
  true_positives: number
  false_positives: number
  false_negatives: number
  precision: number | null
  recall: number | null
  f1: number | null
  tolerance_px: number
  matching: string
  caveats: string[]
}

export interface MatchResult {
  image_a: string
  image_b: string
  stereo_pair: boolean
  width_a: number
  height_a: number
  width_b: number
  height_b: number
  keypoints_a: number
  keypoints_b: number
  tentative: number
  inliers: number
  inlier_ratio: number | null
  disparity: Record<string, number>
  matches: { ax: number; ay: number; bx: number; by: number; inlier: boolean }[]
  elapsed_ms: number
  provenance: Provenance
  notes: string[]
}

export interface StatSummary {
  mean: number
  median: number
  p95: number
}

export interface Benchmark {
  images: number
  cameras: string[]
  methods: {
    method: string
    title: string
    images: number
    runtime_ms: StatSummary | null
    candidates: StatSummary | null
    annotated_images: number
    true_positives: number
    false_positives: number
    false_negatives: number
    precision: number | null
    recall: number | null
    f1: number | null
  }[]
  agreement_f1: StatSummary | null
  notes: string[]
}

// ---- Contract v1.3 (Phase 4: Terrain & Navigation) -------------------------------------------

/** A point in the PLACES DEM projection (metres). */
export interface EN {
  e: number
  n: number
}

export interface Extent {
  e_min: number
  e_max: number
  n_min: number
  n_max: number
}

export interface CostModel {
  max_slope_deg: number
  slope_weight: number
  max_roughness_m: number
  roughness_weight: number
}

export interface TerrainStatus {
  available: boolean
  rows: number
  cols: number
  cell_m: number
  extent: Extent
  bounds_deg: { lon_min: number; lon_max: number; lat_min: number; lat_max: number }
  validation?: { waypoints: number; inside: number; compared: number; median_offset_m?: number; p95_abs_offset_m?: number }
  elevation_m?: { min: number; max: number }
  source: { name: string; url: string; credit: string }
  provenance: Provenance
  notes: string[]
  how_to_get: string | null
}

export interface DrivePath {
  index: number
  sol: number
  from_rmc: string | null
  to_rmc: string | null
  length_m: number | null
  points: [number, number][]
}

export interface TerrainLayer {
  name: 'hillshade' | 'slope' | 'roughness' | 'risk'
  label: string
  url: string
  legend: { label: string; color: string }[]
}

export interface TerrainMap {
  id: string
  center: EN
  size_m: number
  cell_m: number
  grid: [number, number]
  extent: Extent
  cost_model: Record<string, number>
  layers: TerrainLayer[]
  stats: {
    slope_p50_deg: number | null
    slope_p95_deg: number | null
    slope_max_deg: number | null
    roughness_p95_m: number | null
    elevation_min_m: number
    elevation_max_m: number
    risk_fraction: Record<'low' | 'moderate' | 'high' | 'impassable', number>
  }
  drives_in_view: DrivePath[]
  provenance: Provenance
  assumptions: string[]
  limitations: string[]
}

export interface MapRequest {
  center?: EN
  size_m?: number
  drives?: [number, number]
  margin_m?: number
  cost_model?: CostModel
}

export type PlannerName = 'astar' | 'dijkstra' | 'theta_star' | 'rrt_star'

export interface RouteMetrics {
  feasible: boolean
  length_m: number
  impassable_m: number
  cost: number | null
  cost_distance: number
  cost_slope: number
  cost_roughness: number
  max_slope_deg: number
  mean_slope_deg: number
  max_roughness_m: number
  elevation_gain_m: number
  elevation_loss_m: number
  min_clearance_m: number | null
  profile: [number, number][]
}

export interface PlannedRoute {
  planner: PlannerName | 'actual'
  title: string
  kind: 'deterministic' | 'randomized' | 'real_observation'
  found: boolean
  reason: string | null
  points: [number, number][]
  metrics: RouteMetrics | null
  expanded: number
  elapsed_ms: number
  extra: Record<string, number>
}

export interface Plan {
  map: TerrainMap
  start: EN
  goal: EN
  snapped: boolean
  routes: PlannedRoute[]
  actual: PlannedRoute | null
  best: PlannerName | null
  explanation: string[]
  provenance: Provenance
}

export interface PlanRequest {
  map: MapRequest
  start?: EN
  goal?: EN
  planners: PlannerName[]
  rrt_seed: number
  rrt_iterations: number
}

// ---- Contract v1.4 (Phase 5: Mission Replay + AI assistant) ------------------------------

export type SequenceKind = 'fixed_pointing' | 'pointing_sweep' | 'vehicle_fixed' | 'single_exposure' | 'unclassified'

export interface SequenceSummary {
  id: string
  sol: number
  camera: Camera
  sequence_id: string | null
  kind: SequenceKind
  kind_note: string
  frame_count: number
  duration_s: number | null
  median_interval_s: number | null
  distinct_pointings: number | null
  start_lmst: string | null
  thumb_url: string
  label: 'reconstructed'
  provenance: Provenance
}

export interface SequenceFrame {
  image_id: string
  /** Seconds since the first frame, from the spacecraft clock. */
  t_offset_s: number | null
  sclk: number | null
  lmst: string | null
  width: number | null
  height: number | null
  thumb_url: string
  preview_url: string
  provenance: Provenance
}

export interface SequenceDetail extends SequenceSummary {
  frames: SequenceFrame[]
  notes: string[]
  credits: string[]
  real_time_available: boolean
}

export interface SolActivity {
  sol: number
  images: number
  sequences: number
  drives: number
  drive_m: number
}

export interface MissionTimeline {
  sols: SolActivity[]
  total_drive_m: number
  drive_sols: number
  image_sols: number
  provenance: Provenance
  sources: SourceRef[]
  notes: string[]
}

export interface TimelineImage {
  image_id: string
  camera: Camera
  lmst: string | null
  lmst_h: number | null
  sclk: number | null
  sequence_id: string | null
  thumb_url: string
}

export interface TimelineDrive {
  index: number
  from_rmc: string | null
  to_rmc: string | null
  length_m: number | null
  start_lmst_h: number | null
  end_lmst_h: number | null
  provenance: Provenance
}

export interface SolTimeline {
  sol: number
  images: TimelineImage[]
  sequences: SequenceSummary[]
  drives: TimelineDrive[]
  end_of_sol_position: WaypointPoint | null
  lmst_calibration: { samples: number; max_residual_s: number; method: string } | null
  previous_sol: number | null
  next_sol: number | null
  notes: string[]
}

export interface FeaturedSequence {
  key: string
  title: string
  description: string
  sol: number
  camera: Camera
  sequence_id: string
  published_frames: number
  local_frames: number
  sequence_url: string | null
  job_request: IngestJobRequest
  provenance: Provenance
}

export interface OfficialVideo {
  nasa_id: string
  title: string
  date: string
  sol: number | null
  description: string
  credit: string
  video_url: string
  poster_url: string
  page_url: string
  label: 'official_nasa_video'
  provenance: Provenance
}

export interface AssistantStatus {
  enabled: boolean
  model: string
  effort: string
  fallbacks: boolean
  max_tool_rounds: number
  tools: { name: string; description: string }[]
  how_to_enable: string[]
  data_sent: string[]
  never: string[]
  pricing: { model: string; input_usd_per_mtok: number; output_usd_per_mtok: number; note: string }[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatContext {
  page?: string
  sol?: number
  image_id?: string
}

export interface ChatResponse {
  reply: string
  model: string
  stop_reason: string | null
  refused: boolean
  fallback_used: boolean
  rounds: number
  tool_calls: { name: string; input: Record<string, unknown>; is_error: boolean; result_chars: number }[]
  usage: {
    input_tokens: number
    output_tokens: number
    cache_read_input_tokens: number
    cache_creation_input_tokens: number
  }
  notes: string[]
  label: 'ai_generated'
  provenance: Provenance
}
