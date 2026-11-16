import { describe, expect, it } from 'vitest'
import type { WaypointPoint } from '../../api/types'
import { buildTraversePlot, nearestByDistance, profilePoints } from './traverse'

const LANDING = { lat: 18.4447, lon: 77.4508 }

const wp = (sol: number, lat: number, lon: number, elev: number | null, odo: number | null): WaypointPoint => ({
  sol,
  site: 1,
  drive: 0,
  lat,
  lon,
  elevation_m: elev,
  odometry_total_m: odo,
})

const WAYPOINTS = [
  wp(13, 18.44462715, 77.45088572, -2569.91, 0),
  wp(500, 18.45, 77.4, null, 12_000),
  wp(2022, 18.43559434, 77.23322287, -1936.37, 45_245.71),
]

describe('buildTraversePlot', () => {
  it('fits all points inside the box with equal axis scale and north up', () => {
    const plot = buildTraversePlot(WAYPOINTS, LANDING, 320, 190, 14)
    expect(plot).not.toBeNull()
    for (const p of plot!.points) {
      expect(p.sx).toBeGreaterThanOrEqual(14 - 1e-9)
      expect(p.sx).toBeLessThanOrEqual(320 - 14 + 1e-9)
      expect(p.sy).toBeGreaterThanOrEqual(14 - 1e-9)
      expect(p.sy).toBeLessThanOrEqual(190 - 14 + 1e-9)
    }
    const [first, north, west] = plot!.points
    expect(west!.sx).toBeLessThan(first!.sx) // west is left
    expect(north!.sy).toBeLessThan(first!.sy) // north is up
  })

  it('produces a nice scale bar consistent with the scale', () => {
    const plot = buildTraversePlot(WAYPOINTS, LANDING, 320, 190, 14)!
    expect([1, 2, 5]).toContain(plot.scaleBar.metres / 10 ** Math.floor(Math.log10(plot.scaleBar.metres)))
    expect(plot.scaleBar.length).toBeCloseTo(plot.scaleBar.metres * plot.scale)
  })

  it('returns null for no data', () => {
    expect(buildTraversePlot([], LANDING, 320, 190, 14)?.points ?? []).toHaveLength(0)
  })
})

describe('profilePoints', () => {
  it('skips waypoints missing elevation or odometry instead of inventing values', () => {
    const points = profilePoints(WAYPOINTS)
    expect(points.map((p) => p.index)).toEqual([0, 2])
    expect(points[1]!.km).toBeCloseTo(45.24571)
  })
})

describe('nearestByDistance', () => {
  it('finds the closest point', () => {
    const pts = [
      { sx: 0, sy: 0, id: 'a' },
      { sx: 10, sy: 10, id: 'b' },
    ]
    expect(nearestByDistance(pts, 8, 9)?.id).toBe('b')
    expect(nearestByDistance([], 0, 0)).toBeNull()
  })
})
