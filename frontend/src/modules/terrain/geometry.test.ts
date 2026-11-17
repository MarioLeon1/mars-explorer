import { describe, expect, it } from 'vitest'
import { fromFraction, inside, polyline, profileAt, toFraction } from './geometry'

const extent = { e_min: 1000, e_max: 1800, n_min: 5000, n_max: 5800 }

describe('terrain geometry', () => {
  it('maps projected metres to fractions with north up', () => {
    expect(toFraction(extent, 1000, 5800)).toEqual({ x: 0, y: 0 }) // north-west corner
    expect(toFraction(extent, 1800, 5000)).toEqual({ x: 1, y: 1 }) // south-east corner
    expect(toFraction(extent, 1400, 5400)).toEqual({ x: 0.5, y: 0.5 })
  })

  it('round-trips fractions and projected points', () => {
    const p = fromFraction(extent, 0.25, 0.75)
    expect(p).toEqual({ e: 1200, n: 5200 })
    expect(toFraction(extent, p.e, p.n)).toEqual({ x: 0.25, y: 0.75 })
    expect(inside(extent, p)).toBe(true)
    expect(inside(extent, { e: 999, n: 5200 })).toBe(false)
  })

  it('builds SVG polylines in pixel space', () => {
    expect(polyline(extent, [[1000, 5800], [1800, 5000]], 400, 200)).toBe('0.0,0.0 400.0,200.0')
  })

  it('interpolates elevation profiles and refuses to extrapolate', () => {
    const profile: [number, number][] = [[0, -2400], [100, -2390], [200, -2410]]
    expect(profileAt(profile, 50)).toBeCloseTo(-2395)
    expect(profileAt(profile, 150)).toBeCloseTo(-2400)
    expect(profileAt(profile, 250)).toBeNull()
    expect(profileAt([], 0)).toBeNull()
  })
})
