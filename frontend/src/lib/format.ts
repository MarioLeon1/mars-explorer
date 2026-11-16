const DASH = '—'

export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

/** 18.43559434 -> "18.43559° N"; 77.23322287 (lon) -> "77.23322° E". Planetocentric, east-positive. */
export function formatLatitude(lat: number | null | undefined, digits = 5): string {
  if (lat === null || lat === undefined || !Number.isFinite(lat)) return DASH
  return `${Math.abs(lat).toFixed(digits)}° ${lat >= 0 ? 'N' : 'S'}`
}

export function formatLongitude(lon: number | null | undefined, digits = 5): string {
  if (lon === null || lon === undefined || !Number.isFinite(lon)) return DASH
  return `${Math.abs(lon).toFixed(digits)}° ${lon >= 0 ? 'E' : 'W'}`
}

export function formatKilometres(metres: number | null | undefined, digits = 2): string {
  if (metres === null || metres === undefined || !Number.isFinite(metres)) return DASH
  return `${formatNumber(metres / 1000, digits)} km`
}

export function formatMetres(metres: number | null | undefined, digits = 1): string {
  if (metres === null || metres === undefined || !Number.isFinite(metres)) return DASH
  return `${formatNumber(metres, digits)} m`
}

export function formatDegrees(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH
  return `${value.toFixed(digits)}°`
}

/** "2026-10-28T11:17:45.864000Z" -> "2026-10-28 11:17:45 UTC". */
export function formatUtc(iso: string | null | undefined): string {
  if (!iso) return DASH
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return DASH
  return `${date.toISOString().slice(0, 19).replace('T', ' ')} UTC`
}

export function formatUtcDate(iso: string | null | undefined): string {
  if (!iso) return DASH
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? DASH : date.toISOString().slice(0, 10)
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return DASH
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`
}

/** Pad a sol for display: 64 -> "0064". */
export function formatSol(sol: number): string {
  return String(sol).padStart(4, '0')
}

/** "Sol-02024M12:35:01.653" style LMST already parsed by the API; fall back gracefully. */
export function formatLmst(lmst: string | null | undefined): string {
  return lmst ? `${lmst} LMST` : DASH
}

export { DASH }
