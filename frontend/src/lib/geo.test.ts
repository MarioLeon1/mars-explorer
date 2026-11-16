import { describe, expect, it } from 'vitest'
import { boundsOf, formatLength, MARS_RADIUS_M, niceLength, projectLocal } from './geo'

const LANDING = { lat: 18.4447, lon: 77.4508 }

describe('projectLocal', () => {
  it('maps the origin to (0, 0)', () => {
    expect(projectLocal(LANDING, LANDING)).toEqual({ x: 0, y: 0 })
  })

  it('maps one degree of latitude to R·π/180 metres north', () => {
    const p = projectLocal({ lat: LANDING.lat + 1, lon: LANDING.lon }, LANDING)
    expect(p.x).toBeCloseTo(0)
    expect(p.y).toBeCloseTo((MARS_RADIUS_M * Math.PI) / 180, 3) // ≈ 59.27 km
  })

  it('shrinks longitude by cos(latitude) and keeps east positive', () => {
    const p = projectLocal({ lat: LANDING.lat, lon: LANDING.lon + 1 }, LANDING)
    const expected = ((MARS_RADIUS_M * Math.PI) / 180) * Math.cos((LANDING.lat * Math.PI) / 180)
    expect(p.x).toBeCloseTo(expected, 3)
    expect(projectLocal({ lat: LANDING.lat, lon: LANDING.lon - 1 }, LANDING).x).toBeLessThan(0)
  })

  it('puts the sol 2022 localization ~12.2 km west and ~0.5 km south of the landing site', () => {
    const p = projectLocal({ lat: 18.43559434, lon: 77.23322287 }, LANDING)
    expect(p.x / 1000).toBeCloseTo(-12.23, 1)
    expect(p.y / 1000).toBeCloseTo(-0.54, 1)
  })
})

describe('helpers', () => {
  it('computes bounds', () => {
    expect(boundsOf([])).toBeNull()
    expect(boundsOf([{ x: 1, y: -2 }, { x: -3, y: 4 }])).toEqual({ minX: -3, maxX: 1, minY: -2, maxY: 4 })
  })

  it('picks nice scale-bar lengths', () => {
    expect(niceLength(3400)).toBe(2000)
    expect(niceLength(999)).toBe(500)
    expect(niceLength(10)).toBe(10)
    expect(niceLength(0)).toBe(0)
    expect(formatLength(2000)).toBe('2 km')
    expect(formatLength(500)).toBe('500 m')
  })
})
