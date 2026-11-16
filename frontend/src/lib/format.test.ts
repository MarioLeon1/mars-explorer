import { describe, expect, it } from 'vitest'
import {
  DASH,
  formatBytes,
  formatDegrees,
  formatKilometres,
  formatLatitude,
  formatLmst,
  formatLongitude,
  formatMetres,
  formatSol,
  formatUtc,
} from './format'

describe('format', () => {
  it('formats planetocentric coordinates with hemisphere', () => {
    expect(formatLatitude(18.43559434)).toBe('18.43559° N')
    expect(formatLatitude(-4.5, 1)).toBe('4.5° S')
    expect(formatLongitude(77.23322287)).toBe('77.23322° E')
    expect(formatLongitude(-10, 0)).toBe('10° W')
  })

  it('formats distances and angles', () => {
    expect(formatKilometres(45245.71)).toBe('45.25 km')
    expect(formatMetres(-1936.366943)).toBe('-1,936.4 m')
    expect(formatDegrees(93.9657952)).toBe('94.0°')
  })

  it('formats timestamps in UTC regardless of the local timezone', () => {
    expect(formatUtc('2026-10-28T11:17:45.864000Z')).toBe('2026-10-28 11:17:45 UTC')
    expect(formatUtc('not-a-date')).toBe(DASH)
  })

  it('formats sizes, sols and LMST', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(13_677_946)).toBe('13 MB')
    expect(formatBytes(1_500_000)).toBe('1.4 MB')
    expect(formatSol(64)).toBe('0064')
    expect(formatLmst('12:35:01')).toBe('12:35:01 LMST')
  })

  it('renders missing values as a dash, never as zero', () => {
    expect(formatKilometres(null)).toBe(DASH)
    expect(formatLatitude(undefined)).toBe(DASH)
    expect(formatLmst(null)).toBe(DASH)
    expect(formatBytes(Number.NaN)).toBe(DASH)
  })
})
