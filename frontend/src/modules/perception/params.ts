import type { ParamSpec, ParamValue, VisionMethod } from '../../api/types'

export type ParamValues = Record<string, ParamValue>

export function defaultParams(method: VisionMethod): ParamValues {
  return Object.fromEntries(method.params.map((p) => [p.name, p.default]))
}

/** Only parameters that differ from the defaults (keeps requests and cache keys explicit). */
export function changedParams(method: VisionMethod, values: ParamValues): ParamValues {
  return Object.fromEntries(method.params.filter((p) => values[p.name] !== p.default).map((p) => [p.name, values[p.name]!]))
}

/** Clamp and round a numeric input to the spec's bounds; return null for unparsable input. */
export function coerceNumber(spec: ParamSpec, raw: string | number): number | null {
  const value = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(value)) return null
  let result = value
  if (spec.min !== null) result = Math.max(spec.min, result)
  if (spec.max !== null) result = Math.min(spec.max, result)
  if (spec.type === 'int') result = Math.round(result)
  return result
}

export function formatParam(spec: ParamSpec, value: ParamValue): string {
  if (typeof value === 'boolean') return value ? 'on' : 'off'
  if (typeof value === 'number') {
    const decimals = spec.type === 'int' ? 0 : Math.max(0, -Math.floor(Math.log10(spec.step ?? 0.01)))
    return value.toFixed(Math.min(decimals, 3))
  }
  return value
}
