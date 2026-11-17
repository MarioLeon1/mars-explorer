import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { SequenceDetail } from '../../api/types'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { formatNumber } from '../../lib/format'
import {
  defaultMode,
  FPS_OPTIONS,
  formatOffset,
  frameDelay,
  KIND_LABEL,
  MAX_DELAY_MS,
  type PlaybackMode,
  SPEEDS,
} from './playback'

const PRELOAD = 3

export function SequencePlayer({ sequence }: { sequence: SequenceDetail }) {
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [mode, setMode] = useState<PlaybackMode>(defaultMode(sequence.kind, sequence.real_time_available))
  const [speed, setSpeed] = useState<number>(10)
  const [fps, setFps] = useState<number>(5)
  const [loop, setLoop] = useState(true)

  const frames = sequence.frames
  const frame = frames[index]
  const last = frames.length - 1
  const timing = frameDelay(frames, index, mode, speed, fps)

  useEffect(() => {
    if (!playing) return
    const timer = window.setTimeout(() => {
      if (index < last) setIndex(index + 1)
      else if (loop) setIndex(0)
      else setPlaying(false)
    }, timing.delayMs)
    return () => window.clearTimeout(timer)
  }, [playing, index, timing.delayMs, last, loop])

  // Warm the browser cache for the next frames so playback does not stutter.
  useEffect(() => {
    for (let k = 1; k <= PRELOAD; k++) {
      const next = frames[(index + k) % frames.length]
      if (next) new Image().src = next.preview_url
    }
  }, [index, frames])

  if (!frame) return null

  return (
    <div className="rp-player">
      <div className="rp-player__stage">
        <img
          key={frame.image_id}
          src={frame.preview_url}
          alt={`Frame ${index + 1} of ${frames.length}, ${sequence.camera.label}, sol ${sequence.sol}`}
        />
        <span className="rp-player__stamp" aria-live="off">
          RECONSTRUCTED · not a NASA video
        </span>
        <span className="rp-player__counter mono">
          {index + 1}/{frames.length} · {formatOffset(frame.t_offset_s)}
        </span>
      </div>

      <div className="rp-player__controls">
        <button type="button" className="ds-button" onClick={() => setIndex((i) => Math.max(0, i - 1))} aria-label="Previous frame">
          ◀
        </button>
        <button
          type="button"
          className="ds-button rp-player__play"
          onClick={() => {
            if (!playing && index === last) setIndex(0)
            setPlaying((p) => !p)
          }}
        >
          {playing ? 'Pause' : 'Play'}
        </button>
        <button type="button" className="ds-button" onClick={() => setIndex((i) => Math.min(last, i + 1))} aria-label="Next frame">
          ▶
        </button>
        <input
          type="range"
          className="rp-player__scrub"
          min={0}
          max={last}
          value={index}
          onChange={(e) => setIndex(Number(e.target.value))}
          aria-label="Frame"
        />
      </div>

      <div className="rp-player__options">
        <div className="pw__tabs" role="tablist" aria-label="Playback timing">
          <button
            type="button"
            role="tab"
            aria-selected={mode === 'realtime'}
            className={mode === 'realtime' ? 'is-active' : ''}
            disabled={!sequence.real_time_available}
            title={sequence.real_time_available ? 'Real gaps between exposures, sped up' : 'No timing between frames'}
            onClick={() => setMode('realtime')}
          >
            Real timing
          </button>
          <button type="button" role="tab" aria-selected={mode === 'fps'} className={mode === 'fps' ? 'is-active' : ''} onClick={() => setMode('fps')}>
            Fixed rate
          </button>
        </div>
        {mode === 'realtime' ? (
          <label className="rp-inline">
            <span className="label">Speed</span>
            <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
              {SPEEDS.map((s) => (
                <option key={s} value={s}>
                  {s}×
                </option>
              ))}
            </select>
          </label>
        ) : (
          <label className="rp-inline">
            <span className="label">Rate</span>
            <select value={fps} onChange={(e) => setFps(Number(e.target.value))}>
              {FPS_OPTIONS.map((f) => (
                <option key={f} value={f}>
                  {f} fps
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="rp-inline">
          <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} /> Loop
        </label>
        <span className="rp-player__gap">
          {mode === 'realtime' && timing.realGapS !== null && (
            <>
              next exposure <span className="mono">{formatOffset(timing.realGapS).replace('+', '')}</span> later
              {timing.clamped && timing.delayMs === MAX_DELAY_MS && ' · long gap shortened'}
            </>
          )}
        </span>
      </div>

      <div className="rp-player__meta">
        <ProvenanceBadge provenance="derived" />
        <span className="rp-kind">{KIND_LABEL[sequence.kind]}</span>
        <span>
          {sequence.camera.label} · sol <span className="mono">{sequence.sol}</span> · seq{' '}
          <span className="mono">{sequence.sequence_id ?? '—'}</span>
        </span>
        <span>
          span <span className="mono">{formatOffset(sequence.duration_s).replace('+', '')}</span>
          {sequence.median_interval_s !== null && (
            <>
              {' '}
              · median gap <span className="mono">{formatNumber(sequence.median_interval_s, 1)} s</span>
            </>
          )}
        </span>
      </div>
      <div className="rp-player__frame">
        <ProvenanceBadge provenance={frame.provenance} credit={sequence.credits.join(', ') || null} />
        <span>
          Frame <Link to={`/explorer/${frame.image_id}`} className="mono">{frame.image_id}</Link>
        </span>
        <span>
          LMST <span className="mono">{frame.lmst ?? '—'}</span>
        </span>
        <span>
          SCLK <span className="mono">{frame.sclk !== null ? frame.sclk.toFixed(3) : '—'}</span>
        </span>
      </div>
      <ul className="rp-notes">
        {sequence.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  )
}
