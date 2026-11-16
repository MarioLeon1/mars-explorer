/**
 * Local planar projection for schematic traverse plots.
 *
 * Equirectangular projection centred on an origin: x = R·cos(lat0)·Δlon, y = R·Δlat.
 * Over a few tens of km this distorts distances by well under 1 %, which is fine for a
 * schematic plot. It is NOT a map projection suitable for measurement or terrain work.
 * R is the Mars 2000 / IAU sphere radius used by the JPL MMGIS and USGS products.
 */
export const MARS_RADIUS_M = 3_396_190

export interface LatLon {
  lat: number
  lon: number
}

export interface LocalPoint {
  /** metres east of the origin */
  x: number
  /** metres north of the origin */
  y: number
}

const DEG = Math.PI / 180

export function projectLocal(point: LatLon, origin: LatLon): LocalPoint {
  return {
    x: MARS_RADIUS_M * Math.cos(origin.lat * DEG) * (point.lon - origin.lon) * DEG,
    y: MARS_RADIUS_M * (point.lat - origin.lat) * DEG,
  }
}

export interface Bounds {
  minX: number
  maxX: number
  minY: number
  maxY: number
}

export function boundsOf(points: LocalPoint[]): Bounds | null {
  if (points.length === 0) return null
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const { x, y } of points) {
    minX = Math.min(minX, x)
    maxX = Math.max(maxX, x)
    minY = Math.min(minY, y)
    maxY = Math.max(maxY, y)
  }
  return { minX, maxX, minY, maxY }
}

/** Largest "nice" length (1, 2 or 5 × 10^n) that does not exceed `maxLength`. */
export function niceLength(maxLength: number): number {
  if (!(maxLength > 0)) return 0
  const magnitude = 10 ** Math.floor(Math.log10(maxLength))
  for (const step of [5, 2, 1]) {
    if (step * magnitude <= maxLength) return step * magnitude
  }
  return magnitude
}

export function formatLength(metres: number): string {
  return metres >= 1000 ? `${metres / 1000} km` : `${metres} m`
}
