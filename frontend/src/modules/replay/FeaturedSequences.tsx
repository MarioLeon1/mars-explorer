import { useEffect, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { FeaturedSequence, IngestJob } from '../../api/types'

const POLL_MS = 1500
const FINISHED = new Set(['success', 'partial', 'failed', 'cancelled'])

interface Props {
  items: FeaturedSequence[]
  onPlay: (item: FeaturedSequence) => void
  /** Called when a download job finishes so the page can reload what is stored. */
  onDownloaded: () => void
}

export function FeaturedSequences({ items, onPlay, onDownloaded }: Props) {
  const [jobs, setJobs] = useState<Record<string, IngestJob>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})

  const running = Object.entries(jobs).filter(([, job]) => !FINISHED.has(job.status))
  const runningIds = running.map(([, job]) => job.id).join(',')

  useEffect(() => {
    if (!runningIds) return
    const timer = window.setInterval(() => {
      api.jobs().then(
        (list) => {
          const byId = new Map(list.map((j) => [j.id, j]))
          const watched = new Set(runningIds.split(','))
          setJobs((current) => {
            const next = { ...current }
            for (const [key, job] of Object.entries(current)) {
              const fresh = byId.get(job.id)
              if (fresh) next[key] = fresh
            }
            return next
          })
          // Every watched job was still running when this effect started.
          if (list.some((j) => watched.has(j.id) && FINISHED.has(j.status))) onDownloaded()
        },
        () => undefined,
      )
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [runningIds, onDownloaded])

  const download = async (item: FeaturedSequence) => {
    setErrors((e) => ({ ...e, [item.key]: '' }))
    try {
      const job = await api.createJob(item.job_request)
      setJobs((j) => ({ ...j, [item.key]: job }))
    } catch (error) {
      setErrors((e) => ({ ...e, [item.key]: error instanceof ApiError ? error.message : String(error) }))
    }
  }

  return (
    <ul className="rp-list">
      {items.map((item) => {
        const job = jobs[item.key]
        const busy = job !== undefined && !FINISHED.has(job.status)
        const complete = item.local_frames >= item.published_frames
        return (
          <li key={item.key} className="rp-card">
            <p className="rp-card__title">{item.title}</p>
            <p className="rp-card__text">{item.description}</p>
            <p className="rp-card__meta">
              Sol <span className="mono">{item.sol}</span> · {item.camera.label} · stored{' '}
              <span className="mono">
                {item.local_frames}/{item.published_frames}
              </span>{' '}
              frames
            </p>
            <div className="rp-card__actions">
              {item.sequence_url && (
                <button type="button" className="ds-button" onClick={() => onPlay(item)}>
                  Play reconstruction
                </button>
              )}
              {!complete && (
                <button type="button" className="ds-button" disabled={busy} onClick={() => void download(item)}>
                  {busy ? 'Downloading…' : `Download ${item.published_frames} frames from NASA`}
                </button>
              )}
            </div>
            {job && (
              <p className="rp-card__meta" role="status">
                Job <span className="mono">{job.status}</span> · seen <span className="mono">{job.progress.seen}</span> · added{' '}
                <span className="mono">{job.progress.added}</span>
                {job.error && ` · ${job.error}`}
              </p>
            )}
            {errors[item.key] && (
              <p className="rp-card__error" role="alert">
                {errors[item.key]}
              </p>
            )}
          </li>
        )
      })}
    </ul>
  )
}
