import type {
  ApiErrorBody,
  CameraWithCount,
  ImageDetail,
  ImagePage,
  MissionInfo,
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

export async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { signal, headers: { Accept: 'application/json' } })
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
  if (body === null) {
    throw new ApiError(response.status, 'invalid_response', 'The API returned an empty or non-JSON body.')
  }
  return body as T
}

export interface ImageQuery {
  sol?: number
  solMin?: number
  solMax?: number
  cameras?: string[]
  limit?: number
  offset?: number
  order?: 'asc' | 'desc'
}

export function imagesPath(query: ImageQuery = {}): string {
  const params = new URLSearchParams()
  if (query.sol !== undefined) params.set('sol', String(query.sol))
  if (query.solMin !== undefined) params.set('sol_min', String(query.solMin))
  if (query.solMax !== undefined) params.set('sol_max', String(query.solMax))
  for (const camera of query.cameras ?? []) params.append('camera', camera)
  if (query.limit !== undefined) params.set('limit', String(query.limit))
  if (query.offset !== undefined) params.set('offset', String(query.offset))
  if (query.order) params.set('order', query.order)
  const qs = params.toString()
  return qs ? `/api/images?${qs}` : '/api/images'
}

export const api = {
  mission: (signal?: AbortSignal) => request<MissionInfo>('/api/mission', signal),
  cameras: (signal?: AbortSignal) => request<CameraWithCount[]>('/api/cameras', signal),
  sols: (signal?: AbortSignal) => request<SolSummary[]>('/api/sols', signal),
  images: (query: ImageQuery, signal?: AbortSignal) => request<ImagePage>(imagesPath(query), signal),
  image: (id: string, signal?: AbortSignal) =>
    request<ImageDetail>(`/api/images/${encodeURIComponent(id)}`, signal),
  roverPosition: (signal?: AbortSignal) => request<RoverPosition>('/api/rover/position', signal),
  waypoints: (signal?: AbortSignal) => request<WaypointList>('/api/rover/waypoints', signal),
  systemStatus: (signal?: AbortSignal) => request<SystemStatus>('/api/system/status', signal),
}
