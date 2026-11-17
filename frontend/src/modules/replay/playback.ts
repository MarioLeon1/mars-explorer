import type { SequenceFrame, SequenceKind } from '../../api/types'

/**
 * Playback timing for reconstructed sequences.
 *
 * - `realtime`: the delay between frames is the real gap between exposures (from the spacecraft
 *   clock) divided by `speed`. Long gaps are capped so playback never stalls; the UI says so.
 * - `fps`: a constant frame rate, ignoring real timing (useful for sweeps and single exposures).
 */
export type PlaybackMode = 'realtime' | 'fps'

export const MIN_DELAY_MS = 40
export const MAX_DELAY_MS = 3000
export const SPEEDS = [1, 4, 10, 30] as const
export const FPS_OPTIONS = [2, 5, 10] as const

export interface FrameDelay {
  delayMs: number
  /** Real time between this frame and the next, seconds (null if unknown). */
  realGapS: number | null
  /** The real-time delay had to be clamped to [MIN_DELAY_MS, MAX_DELAY_MS]. */
  clamped: boolean
}

export function frameDelay(
  frames: readonly Pick<SequenceFrame, 't_offset_s'>[],
  index: number,
  mode: PlaybackMode,
  speed: number,
  fps: number,
): FrameDelay {
  const current = frames[index]?.t_offset_s ?? null
  const next = frames[index + 1]?.t_offset_s ?? null
  const realGapS = current !== null && next !== null ? Math.max(0, next - current) : null
  if (mode === 'fps' || realGapS === null) {
    return { delayMs: Math.round(1000 / Math.max(fps, 0.1)), realGapS, clamped: false }
  }
  const raw = (realGapS * 1000) / Math.max(speed, 0.01)
  const delayMs = Math.min(MAX_DELAY_MS, Math.max(MIN_DELAY_MS, raw))
  return { delayMs: Math.round(delayMs), realGapS, clamped: delayMs !== raw }
}

/** Default mode: real time only when it means something (a time series with real gaps). */
export function defaultMode(kind: SequenceKind, realTimeAvailable: boolean): PlaybackMode {
  if (!realTimeAvailable) return 'fps'
  return kind === 'fixed_pointing' || kind === 'vehicle_fixed' ? 'realtime' : 'fps'
}

export const KIND_LABEL: Record<SequenceKind, string> = {
  fixed_pointing: 'Fixed pointing',
  pointing_sweep: 'Pointing sweep',
  vehicle_fixed: 'Vehicle-fixed camera',
  single_exposure: 'Single exposure',
  unclassified: 'Unclassified',
}

/** "+1 m 25 s" style offset for a frame. */
export function formatOffset(seconds: number | null): string {
  if (seconds === null) return '—'
  const total = Math.round(seconds * 10) / 10
  if (total < 60) return `+${total.toFixed(1)} s`
  const minutes = Math.floor(total / 60)
  const rest = Math.round(total - minutes * 60)
  if (minutes < 60) return `+${minutes} m ${String(rest).padStart(2, '0')} s`
  const hours = Math.floor(minutes / 60)
  return `+${hours} h ${String(minutes % 60).padStart(2, '0')} m`
}

/** Pick a readable LMST window around the events (at least 4 h, within 0–24). */
export function lmstWindow(hours: number[]): [number, number] {
  if (hours.length === 0) return [6, 18]
  let low = Math.floor(Math.min(...hours) - 0.5)
  let high = Math.ceil(Math.max(...hours) + 0.5)
  while (high - low < 4) {
    low -= 1
    high += 1
  }
  return [Math.max(0, low), Math.min(24, high)]
}

/** LMST hour (0–24.x) as HH:MM. */
export function formatLmstHours(hours: number | null): string {
  if (hours === null) return '—'
  const wrapped = ((hours % 24) + 24) % 24
  const h = Math.floor(wrapped)
  const m = Math.floor((wrapped - h) * 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}
