import { filterParams, type ImageFilters } from '../../api/client'

const DATE = /^\d{4}-\d{2}-\d{2}$/

function readInt(params: URLSearchParams, key: string): number | undefined {
  const raw = params.get(key)
  if (raw === null || raw.trim() === '') return undefined
  const value = Number(raw)
  return Number.isInteger(value) && value >= 0 ? value : undefined
}

function readDate(params: URLSearchParams, key: string): string | undefined {
  const raw = params.get(key)
  return raw && DATE.test(raw) ? raw : undefined
}

/** Parse Explorer filters from the URL. Invalid values are dropped, never guessed. */
export function readFilters(params: URLSearchParams): ImageFilters {
  const filters: ImageFilters = {}
  const sol = readInt(params, 'sol')
  const solMin = readInt(params, 'sol_min')
  const solMax = readInt(params, 'sol_max')
  const dateFrom = readDate(params, 'date_from')
  const dateTo = readDate(params, 'date_to')
  const cameras = [...new Set(params.getAll('camera').filter((c) => /^[A-Z0-9_]+$/.test(c)))]
  const q = params.get('q')?.trim()
  if (sol !== undefined) filters.sol = sol
  if (solMin !== undefined) filters.solMin = solMin
  if (solMax !== undefined) filters.solMax = solMax
  if (dateFrom) filters.dateFrom = dateFrom
  if (dateTo) filters.dateTo = dateTo
  if (cameras.length) filters.cameras = cameras.sort()
  if (q) filters.q = q.slice(0, 80)
  return filters
}

/** Same keys as the API, so a filtered Explorer URL maps 1:1 to the backend query. */
export function writeFilters(filters: ImageFilters): URLSearchParams {
  return filterParams(filters)
}

export function filtersKey(filters: ImageFilters): string {
  return writeFilters(filters).toString()
}

export function hasFilters(filters: ImageFilters): boolean {
  return filtersKey(filters) !== ''
}

export function describeFilters(filters: ImageFilters): string {
  const parts: string[] = []
  if (filters.sol !== undefined) parts.push(`sol ${filters.sol}`)
  if (filters.solMin !== undefined || filters.solMax !== undefined)
    parts.push(`sols ${filters.solMin ?? 0}–${filters.solMax ?? '…'}`)
  if (filters.cameras?.length) parts.push(filters.cameras.join(', '))
  if (filters.dateFrom || filters.dateTo) parts.push(`${filters.dateFrom ?? '…'} → ${filters.dateTo ?? '…'} UTC`)
  if (filters.q) parts.push(`id contains “${filters.q}”`)
  return parts.length ? parts.join(' · ') : 'all stored images'
}
