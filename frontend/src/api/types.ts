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
