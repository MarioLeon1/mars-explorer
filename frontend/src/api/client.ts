import type {
  PathSketch,
  PathSketchRequest,
  AssistantStatus,
  ChatContext,
  ChatMessage,
  ChatResponse,
  FeaturedSequence,
  MissionTimeline,
  OfficialVideo,
  SequenceDetail,
  SequenceSummary,
  SolTimeline,
  Annotation,
  DrivePath,
  MapRequest,
  Plan,
  PlanRequest,
  TerrainMap,
  TerrainStatus,
  ApiErrorBody,
  Benchmark,
  Evaluation,
  MatchResult,
  ParamValue,
  VisionAnalysis,
  VisionMethod,
  CameraWithCount,
  FeedAvailability,
  ImageDetail,
  ImagePage,
  ImageSummary,
  IngestJob,
  IngestJobRequest,
  MissionInfo,
  Neighbors,
  RawRecord,
  RelatedImages,
  RoverPosition,
  SolSummary,
  SystemStatus,
  WaypointList,
} from './types'

/** An error from the Mars Explorer API, or a network failure reaching it (status 0). */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }

  /** True when the backend itself could not be reached (not running, proxy error). */
  get isUnreachable(): boolean {
    return this.status === 0 || this.code === 'backend_unreachable'
  }
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const error = (value as { error: unknown }).error
  return typeof error === 'object' && error !== null && 'code' in error && 'message' in error
}

interface RequestOptions {
  signal?: AbortSignal
  method?: 'GET' | 'POST' | 'DELETE'
  body?: unknown
}

export async function request<T>(path: string, signalOrOptions?: AbortSignal | RequestOptions): Promise<T> {
  const options: RequestOptions =
    signalOrOptions instanceof AbortSignal ? { signal: signalOrOptions } : (signalOrOptions ?? {})
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(path, {
      signal: options.signal,
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new ApiError(0, 'backend_unreachable', 'Cannot reach the Mars Explorer API.')
  }

  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = null
    }
  }

  if (!response.ok) {
    if (isErrorBody(body)) {
      throw new ApiError(response.status, body.error.code, body.error.message)
    }
    // Vite's dev proxy answers 500/502/504 with no JSON when the backend is down.
    const unreachable = response.status >= 500 && body === null
    throw new ApiError(
      response.status,
      unreachable ? 'backend_unreachable' : 'http_error',
      unreachable ? 'Cannot reach the Mars Explorer API.' : `HTTP ${response.status}`,
    )
  }
  if (response.status === 204) return undefined as T
  if (body === null) {
    throw new ApiError(response.status, 'invalid_response', 'The API returned an empty or non-JSON body.')
  }
  return body as T
}

/** Filters shared by listing and chronological navigation (mirrors the backend ImageFilter). */
export interface ImageFilters {
  sol?: number
  solMin?: number
  solMax?: number
  cameras?: string[]
  dateFrom?: string
  dateTo?: string
  q?: string
}

export interface ImageQuery extends ImageFilters {
  limit?: number
  offset?: number
  order?: 'asc' | 'desc'
}

export function filterParams(filters: ImageFilters, params = new URLSearchParams()): URLSearchParams {
  if (filters.sol !== undefined) params.set('sol', String(filters.sol))
  if (filters.solMin !== undefined) params.set('sol_min', String(filters.solMin))
  if (filters.solMax !== undefined) params.set('sol_max', String(filters.solMax))
  for (const camera of filters.cameras ?? []) params.append('camera', camera)
  if (filters.dateFrom) params.set('date_from', filters.dateFrom)
  if (filters.dateTo) params.set('date_to', filters.dateTo)
  if (filters.q) params.set('q', filters.q)
  return params
}

function withQuery(path: string, params: URLSearchParams): string {
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

export function imagesPath(query: ImageQuery = {}): string {
  const params = filterParams(query)
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  if (query.offset !== undefined) params.set('offset', String(query.offset))
  if (query.order) params.set('order', query.order)
  return withQuery('/api/images', params)
}

const imagePath = (id: string) => `/api/images/${encodeURIComponent(id)}`

export const api = {
  mission: (signal?: AbortSignal) => request<MissionInfo>('/api/mission', signal),
  cameras: (signal?: AbortSignal) => request<CameraWithCount[]>('/api/cameras', signal),
  sols: (signal?: AbortSignal) => request<SolSummary[]>('/api/sols', signal),
  images: (query: ImageQuery, signal?: AbortSignal) => request<ImagePage>(imagesPath(query), signal),
  image: (id: string, signal?: AbortSignal) => request<ImageDetail>(imagePath(id), signal),
  neighbors: (id: string, filters: ImageFilters, signal?: AbortSignal) =>
    request<Neighbors>(withQuery(`${imagePath(id)}/neighbors`, filterParams(filters)), signal),
  related: (id: string, signal?: AbortSignal) => request<RelatedImages>(`${imagePath(id)}/related`, signal),
  raw: (id: string, signal?: AbortSignal) => request<RawRecord>(`${imagePath(id)}/raw`, signal),
  fetchStereoPartner: (id: string) =>
    request<ImageSummary>(`${imagePath(id)}/stereo-partner`, { method: 'POST' }),
  roverPosition: (signal?: AbortSignal) => request<RoverPosition>('/api/rover/position', signal),
  waypoints: (signal?: AbortSignal) => request<WaypointList>('/api/rover/waypoints', signal),
  systemStatus: (signal?: AbortSignal) => request<SystemStatus>('/api/system/status', signal),
  availability: (solMin: number, solMax: number, cameras: string[], signal?: AbortSignal) => {
    const params = new URLSearchParams({ sol_min: String(solMin), sol_max: String(solMax) })
    for (const camera of cameras) params.append('camera', camera)
    return request<FeedAvailability>(withQuery('/api/feed/availability', params), signal)
  },
  createJob: (body: IngestJobRequest) => request<IngestJob>('/api/ingest/jobs', { method: 'POST', body }),
  jobs: (signal?: AbortSignal) => request<IngestJob[]>('/api/ingest/jobs', signal),
  visionMethods: (signal?: AbortSignal) => request<VisionMethod[]>('/api/vision/methods', signal),
  analyze: (imageId: string, method: string, params: Record<string, ParamValue>) =>
    request<VisionAnalysis>('/api/vision/analyses', {
      method: 'POST',
      body: { image_id: imageId, method, params, rendition: 'large' },
    }),
  evaluation: (analysisId: string, signal?: AbortSignal) =>
    request<Evaluation>(`/api/vision/analyses/${encodeURIComponent(analysisId)}/evaluation`, signal),
  annotations: (imageId: string, signal?: AbortSignal) =>
    request<Annotation[]>(`${imagePath(imageId)}/annotations`, signal),
  addAnnotation: (imageId: string, x: number, y: number) =>
    request<Annotation>(`${imagePath(imageId)}/annotations`, { method: 'POST', body: { x, y, label: 'rock' } }),
  deleteAnnotation: (id: number) => request<void>(`/api/annotations/${id}`, { method: 'DELETE' }),
  match: (imageA: string, imageB: string) =>
    request<MatchResult>('/api/vision/match', { method: 'POST', body: { image_a: imageA, image_b: imageB } }),
  terrainStatus: (signal?: AbortSignal) => request<TerrainStatus>('/api/terrain/status', signal),
  drives: (stepM: number, signal?: AbortSignal) => request<DrivePath[]>(`/api/terrain/drives?step_m=${stepM}`, signal),
  terrainMap: (body: MapRequest) => request<TerrainMap>('/api/terrain/maps', { method: 'POST', body }),
  plan: (body: PlanRequest) => request<Plan>('/api/navigation/plans', { method: 'POST', body }),
  pathSketch: (body: PathSketchRequest) => request<PathSketch>('/api/vision/path-sketch', { method: 'POST', body }),
  replayMission: (signal?: AbortSignal) => request<MissionTimeline>('/api/replay/mission', signal),
  replaySol: (sol: number, signal?: AbortSignal) => request<SolTimeline>(`/api/replay/sols/${sol}`, signal),
  sequences: (sol: number | null, signal?: AbortSignal) =>
    request<SequenceSummary[]>(sol === null ? '/api/replay/sequences' : `/api/replay/sequences?sol=${sol}`, signal),
  sequence: (id: string, signal?: AbortSignal) =>
    request<SequenceDetail>(`/api/replay/sequences/${encodeURIComponent(id)}`, signal),
  featured: (signal?: AbortSignal) => request<FeaturedSequence[]>('/api/replay/featured', signal),
  videos: (signal?: AbortSignal) => request<OfficialVideo[]>('/api/replay/videos', signal),
  assistantStatus: (signal?: AbortSignal) => request<AssistantStatus>('/api/assistant/status', signal),
  chat: (messages: ChatMessage[], context?: ChatContext) =>
    request<ChatResponse>('/api/assistant/chat', { method: 'POST', body: { messages, context } }),
  benchmark: (cameras: string[], limit: number) =>
    request<Benchmark>('/api/vision/benchmark', { method: 'POST', body: { cameras, limit } }),
}
