import { describe, expect, it } from 'vitest'
import type { ParamSpec, VisionMethod } from '../../api/types'
import { changedParams, coerceNumber, defaultParams, formatParam } from './params'

const radius: ParamSpec = {
  name: 'min_radius', label: 'Min radius', type: 'float', default: 6, help: '', min: 2, max: 60, step: 1, choices: [],
}
const k: ParamSpec = { name: 'k', label: 'Classes', type: 'int', default: 3, help: '', min: 2, max: 5, step: 1, choices: [] }
const relative: ParamSpec = { name: 'relative', label: 'Relative', type: 'bool', default: true, help: '', min: null, max: null, step: null, choices: [] }
const method: VisionMethod = {
  name: 'm', title: 'M', category: 'detection', kind: 'algorithmic', summary: '', params: [radius, k, relative],
  limitations: [], score_definition: null, experimental: false, produces_detections: true,
}

describe('perception params', () => {
  it('builds defaults and sends only changed values', () => {
    const values = defaultParams(method)
    expect(values).toEqual({ min_radius: 6, k: 3, relative: true })
    expect(changedParams(method, { ...values, k: 4 })).toEqual({ k: 4 })
  })

  it('clamps and rounds numbers to the declared bounds', () => {
    expect(coerceNumber(radius, '100')).toBe(60)
    expect(coerceNumber(radius, 0)).toBe(2)
    expect(coerceNumber(k, 3.6)).toBe(4)
    expect(coerceNumber(radius, 'abc')).toBeNull()
  })

  it('formats values for display', () => {
    expect(formatParam(radius, 6)).toBe('6') // decimals follow the slider step (1)
    expect(formatParam({ ...radius, step: 0.05 }, 0.9)).toBe('0.90')
    expect(formatParam(k, 3)).toBe('3')
    expect(formatParam(relative, false)).toBe('off')
  })
})
