import { describe, expect, it } from 'vitest'
import { defaultMode, lmstWindow, formatLmstHours, formatOffset, frameDelay, MAX_DELAY_MS, MIN_DELAY_MS } from './playback'

const frames = [{ t_offset_s: 0 }, { t_offset_s: 25 }, { t_offset_s: 25.01 }, { t_offset_s: 600 }, { t_offset_s: null }]

describe('frameDelay', () => {
  it('uses the real gap divided by speed', () => {
    expect(frameDelay(frames, 0, 'realtime', 10, 5)).toEqual({ delayMs: 2500, realGapS: 25, clamped: false })
  })

  it('clamps very short and very long gaps and says so', () => {
    expect(frameDelay(frames, 1, 'realtime', 1, 5)).toMatchObject({ delayMs: MIN_DELAY_MS, clamped: true })
    expect(frameDelay(frames, 2, 'realtime', 1, 5)).toMatchObject({ delayMs: MAX_DELAY_MS, clamped: true })
  })

  it('falls back to fps when timing is unknown or fps mode is chosen', () => {
    expect(frameDelay(frames, 3, 'realtime', 1, 5)).toMatchObject({ delayMs: 200, realGapS: null })
    expect(frameDelay(frames, 0, 'fps', 1, 10)).toMatchObject({ delayMs: 100, realGapS: 25, clamped: false })
  })
})

describe('defaultMode', () => {
  it('plays time series in real time and sweeps at a fixed rate', () => {
    expect(defaultMode('fixed_pointing', true)).toBe('realtime')
    expect(defaultMode('vehicle_fixed', true)).toBe('realtime')
    expect(defaultMode('pointing_sweep', true)).toBe('fps')
    expect(defaultMode('fixed_pointing', false)).toBe('fps')
  })
})

describe('lmstWindow', () => {
  it('pads the events, keeps at least 4 h and stays within the sol', () => {
    expect(lmstWindow([])).toEqual([6, 18])
    expect(lmstWindow([11.2, 16.4])).toEqual([10, 17])
    expect(lmstWindow([12.0])).toEqual([10, 14])
    expect(lmstWindow([0.2, 23.9])).toEqual([0, 24])
  })
})

describe('formatting', () => {
  it('formats offsets and LMST hours', () => {
    expect(formatOffset(null)).toBe('—')
    expect(formatOffset(3.44)).toBe('+3.4 s')
    expect(formatOffset(85)).toBe('+1 m 25 s')
    expect(formatOffset(44026)).toBe('+12 h 13 m')
    expect(formatLmstHours(16.5)).toBe('16:30')
    expect(formatLmstHours(24.25)).toBe('00:15')
    expect(formatLmstHours(null)).toBe('—')
  })
})
