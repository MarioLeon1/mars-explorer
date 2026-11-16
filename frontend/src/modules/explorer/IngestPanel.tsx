import { useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { FeedAvailability, IngestJob } from '../../api/types'
import { formatNumber } from '../../lib/format'

/** Cameras offered for download; the full catalogue stays available through the CLI. */
const DOWNLOAD_CAMERAS = [
  'NAVCAM_LEFT',
  'NAVCAM_RIGHT',
  'FRONT_HAZCAM_LEFT_A',
  'FRONT_HAZCAM_RIGHT_A',
  'REAR_HAZCAM_LEFT',
  'MCZ_LEFT',
  'MCZ_RIGHT',
  'SKYCAM',
  'SUPERCAM_RMI',
  'SHERLOC_WATSON',
] as const

const ACTIVE = new Set(['queued', 'running'])
const POLL_MS = 1000

interface IngestPanelProps {
  defaultSol?: number
  /** Called when a job finishes so the archive views reload. */
  onDataChanged: () => void
}

function parseSol(value: string): number | null {
  const n = Number(value)
  return value.trim() !== '' && Number.isInteger(n) && n >= 0 ? n : null
}

function JobRow({ job }: { job: IngestJob }) {
  const done = !ACTIVE.has(job.status)
  const fraction = Math.min(1, job.progress.seen / job.limit)
  const span = job.sol_min === job.sol_max ? `sol ${job.sol_min}` : `sols ${job.sol_min}–${job.sol_max}`
  return (
    <li className={`xi__job xi__job--${job.status}`}>
      <div className="xi__jobhead">
        <span className="mono">{span}</span>
        <span className="xi__status">{job.status}</span>
      </div>
      <div
        className="xi__progress"
        role="progressbar"
        aria-label={`Ingestion of ${span}`}
        aria-valuemin={0}
        aria-valuemax={job.limit}
        aria-valuenow={job.progress.seen}
      >
        <span style={{ width: `${(done ? 1 : fraction) * 100}%` }} />
      </div>
      <p className="xi__counts mono">
        {job.progress.added} new · {job.progress.skipped} already stored · {job.progress.failed} failed
      </p>
      {job.error && done && <p className="xi__error">{job.error.split('\n')[0]}</p>}
    </li>
  )
}

export function IngestPanel({ defaultSol, onDataChanged }: IngestPanelProps) {
  const [open, setOpen] = useState(false)
  const [solMin, setSolMin] = useState(defaultSol?.toString() ?? '')
  const [solMax, setSolMax] = useState('')
  const [cameras, setCameras] = useState<string[]>(['NAVCAM_LEFT', 'NAVCAM_RIGHT'])
  const [limit, setLimit] = useState('40')
  const [availability, setAvailability] = useState<FeedAvailability | null>(null)
  const [checking, setChecking] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [jobs, setJobs] = useState<IngestJob[]>([])
  /** Jobs seen queued/running by this panel; when one finishes, the archive reloads. */
  const watching = useRef(new Set<string>())

  const low = parseSol(solMin)
  const high = solMax.trim() === '' ? low : parseSol(solMax)
  const limitValue = Number(limit)
  const valid = low !== null && high !== null && high >= low && high - low <= 30 && Number.isInteger(limitValue) && limitValue >= 1 && limitValue <= 200

  // Poll while any job is active; reload the archive when a job finishes.
  const anyActive = jobs.some((job) => ACTIVE.has(job.status))
  useEffect(() => {
    if (!open && !anyActive) return
    let cancelled = false
    const tick = () =>
      api.jobs().then(
        (list) => {
          if (cancelled) return
          setJobs(list)
          let changed = false
          for (const job of list) {
            if (ACTIVE.has(job.status)) watching.current.add(job.id)
            else if (watching.current.delete(job.id) && job.progress.added > 0) changed = true
          }
          if (changed) onDataChanged()
        },
        () => undefined,
      )
    tick()
    if (!anyActive) return () => void (cancelled = true)
    const timer = window.setInterval(tick, POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [open, anyActive, onDataChanged])

  const check = async () => {
    if (!valid || low === null || high === null) return
    setChecking(true)
    setMessage(null)
    try {
      setAvailability(await api.availability(low, high, cameras))
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : String(error))
    } finally {
      setChecking(false)
    }
  }

  const start = async () => {
    if (!valid || low === null || high === null) return
    setMessage(null)
    try {
      const job = await api.createJob({ sol_min: low, sol_max: high, cameras, limit: limitValue, full_res: false })
      watching.current.add(job.id)
      setJobs((current) => [job, ...current.filter((j) => j.id !== job.id)])
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : String(error))
    }
  }

  const toggle = (camera: string) =>
    setCameras((current) => (current.includes(camera) ? current.filter((c) => c !== camera) : [...current, camera].sort()))

  return (
    <section className="xi">
      <button type="button" className="xi__toggle" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span className="label">Add data from NASA</span>
        <span aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="xi__body">
          <div className="xf__pair">
            <label className="xf__field">
              <span className="label">Sol</span>
              <input inputMode="numeric" value={solMin} onChange={(e) => { setSolMin(e.target.value); setAvailability(null) }} placeholder="e.g. 1201" />
            </label>
            <label className="xf__field">
              <span className="label">To (optional)</span>
              <input inputMode="numeric" value={solMax} onChange={(e) => { setSolMax(e.target.value); setAvailability(null) }} />
            </label>
          </div>
          <fieldset className="xf__group">
            <legend className="xf__legend">Cameras (none = all)</legend>
            {DOWNLOAD_CAMERAS.map((camera) => (
              <label key={camera} className="xf__check">
                <input type="checkbox" checked={cameras.includes(camera)} onChange={() => { toggle(camera); setAvailability(null) }} />
                <span className="xf__name">{camera.replace(/_/g, ' ')}</span>
              </label>
            ))}
          </fieldset>
          <label className="xf__field">
            <span className="label">Max images (1–200)</span>
            <input inputMode="numeric" value={limit} onChange={(e) => setLimit(e.target.value)} />
          </label>
          {!valid && solMin !== '' && <p className="xi__hint">Use whole sols, at most 31 per download, and 1–200 images.</p>}
          <div className="xi__actions">
            <button type="button" className="ds-button" onClick={check} disabled={!valid || checking}>
              {checking ? 'Checking…' : 'Check NASA'}
            </button>
            <button type="button" className="ds-button xi__go" onClick={start} disabled={!valid}>
              Download
            </button>
          </div>
          {availability && (
            <p className="xi__avail mono" role="status">
              NASA publishes {availability.published === null ? '?' : formatNumber(availability.published)} · {availability.stored} stored
              {availability.published === 0 && <span className="xi__hint"> No images for this sol/camera selection — try other cameras or a neighbouring sol.</span>}
            </p>
          )}
          {message && <p className="xi__error" role="alert">{message}</p>}
          {jobs.length > 0 && (
            <ul className="xi__jobs" aria-label="Recent downloads">
              {jobs.slice(0, 4).map((job) => (
                <JobRow key={job.id} job={job} />
              ))}
            </ul>
          )}
          <p className="xi__fine">Downloads run one at a time with polite pauses. Images come from NASA's public raw-images feed (NASA/JPL-Caltech).</p>
        </div>
      )}
    </section>
  )
}
