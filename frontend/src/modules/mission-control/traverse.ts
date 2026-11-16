import type { WaypointPoint } from '../../api/types'
import { boundsOf, niceLength, projectLocal, type LatLon } from '../../lib/geo'

export interface PlotPoint {
  /** index into the waypoint list */
  index: number
  sx: number
  sy: number
}

export interface TraversePlot {
  points: PlotPoint[]
  origin: { sx: number; sy: number }
  /** svg units per metre (same on both axes: the plot is never stretched) */
  scale: number
  scaleBar: { metres: number; length: number }
}

/** Fit the projected traverse into a width×height box with equal axis scale (north up). */
export function buildTraversePlot(
  waypoints: WaypointPoint[],
  origin: LatLon,
  width: number,
  height: number,
  padding: number,
): TraversePlot | null {
  const projected = waypoints.map((w) => projectLocal(w, origin))
  const bounds = boundsOf([...projected, { x: 0, y: 0 }])
  if (!bounds) return null
  const spanX = Math.max(bounds.maxX - bounds.minX, 1)
  const spanY = Math.max(bounds.maxY - bounds.minY, 1)
  const scale = Math.min((width - 2 * padding) / spanX, (height - 2 * padding) / spanY)
  const offsetX = (width - spanX * scale) / 2
  const offsetY = (height - spanY * scale) / 2
  const toSvg = (x: number, y: number) => ({
    sx: offsetX + (x - bounds.minX) * scale,
    sy: height - (offsetY + (y - bounds.minY) * scale),
  })
  const metres = niceLength((width * 0.28) / scale)
  return {
    points: projected.map((p, index) => ({ index, ...toSvg(p.x, p.y) })),
    origin: toSvg(0, 0),
    scale,
    scaleBar: { metres, length: metres * scale },
  }
}

export interface ProfilePoint {
  index: number
  km: number
  elevation: number
}

/**
 * Waypoints that have both odometry and elevation, sorted by distance, for the
 * elevation-vs-distance profile. Fixes without odometry (e.g. mid-drive) are skipped.
 */
export function profilePoints(waypoints: WaypointPoint[]): ProfilePoint[] {
  const points: ProfilePoint[] = []
  waypoints.forEach((w, index) => {
    if (w.odometry_total_m !== null && w.elevation_m !== null) {
      points.push({ index, km: w.odometry_total_m / 1000, elevation: w.elevation_m })
    }
  })
  return points.sort((a, b) => a.km - b.km)
}

export function nearestByDistance<T extends { sx: number; sy: number }>(points: T[], x: number, y: number): T | null {
  let best: T | null = null
  let bestD = Infinity
  for (const p of points) {
    const d = (p.sx - x) ** 2 + (p.sy - y) ** 2
    if (d < bestD) {
      bestD = d
      best = p
    }
  }
  return best
}
