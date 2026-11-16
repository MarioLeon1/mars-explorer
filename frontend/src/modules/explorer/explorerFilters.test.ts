import { describe, expect, it } from 'vitest'
import { describeFilters, filtersKey, hasFilters, readFilters, writeFilters } from './explorerFilters'

describe('explorer URL filters', () => {
  it('round-trips through the URL with API-compatible keys', () => {
    const filters = {
      solMin: 1000,
      solMax: 1503,
      cameras: ['MCZ_LEFT', 'NAVCAM_LEFT'],
      dateFrom: '2023-01-01',
      dateTo: '2025-12-31',
      q: 'NCAM',
    }
    const params = writeFilters(filters)
    expect(params.toString()).toBe(
      'sol_min=1000&sol_max=1503&camera=MCZ_LEFT&camera=NAVCAM_LEFT&date_from=2023-01-01&date_to=2025-12-31&q=NCAM',
    )
    expect(readFilters(params)).toEqual(filters)
  })

  it('drops invalid values instead of guessing', () => {
    const params = new URLSearchParams('sol=-3&sol_min=abc&date_from=2023-13&camera=bad camera&camera=NAVCAM_LEFT&q=  ')
    expect(readFilters(params)).toEqual({ cameras: ['NAVCAM_LEFT'] })
  })

  it('normalises camera order and duplicates so equal filters share a key', () => {
    const a = readFilters(new URLSearchParams('camera=NAVCAM_LEFT&camera=MCZ_LEFT&camera=MCZ_LEFT'))
    const b = readFilters(new URLSearchParams('camera=MCZ_LEFT&camera=NAVCAM_LEFT'))
    expect(filtersKey(a)).toBe(filtersKey(b))
  })

  it('describes filters for humans', () => {
    expect(hasFilters({})).toBe(false)
    expect(describeFilters({})).toBe('all stored images')
    expect(describeFilters({ sol: 2022, cameras: ['NAVCAM_LEFT'] })).toBe('sol 2022 · NAVCAM_LEFT')
  })
})
