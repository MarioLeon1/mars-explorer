import { useEffect, useState } from 'react'
import { StatusPip, type PipState } from '../design-system/primitives'
import { formatSol } from '../lib/format'
import { useSystemStatus } from './systemStatus'

function useUtcClock(): string {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return now.toISOString().slice(0, 19).replace('T', ' ')
}

export function TopBar() {
  const clock = useUtcClock()
  const { state } = useSystemStatus()
  const status = state.data

  const apiState: PipState = state.status === 'error' ? 'error' : status ? 'ok' : 'idle'
  const dbState: PipState = !status ? 'idle' : status.database.images > 0 ? 'ok' : 'warn'
  const feedState: PipState = !status?.feed
    ? 'idle'
    : status.last_ingest?.status === 'failed'
      ? 'warn'
      : 'ok'

  return (
    <header className="topbar">
      <div className="topbar__brand">
        <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
          <circle cx="16" cy="16" r="9" fill="none" stroke="var(--accent)" strokeWidth="2" />
          <path d="M7 16h4M21 16h4M16 7v4M16 21v4" stroke="var(--text-0)" strokeWidth="1.6" strokeLinecap="round" />
          <circle cx="16" cy="16" r="2" fill="var(--signal)" />
        </svg>
        <span className="topbar__wordmark">MARS EXPLORER</span>
      </div>
      <div className="topbar__mission label">
        Mars 2020 <span aria-hidden="true">·</span> Perseverance <span aria-hidden="true">·</span> Jezero
        crater
      </div>

      <dl className="topbar__readouts">
        <div>
          <dt className="label">Earth UTC</dt>
          <dd className="mono">{clock}</dd>
        </div>
        <div>
          <dt className="label">Archive</dt>
          <dd className="mono">
            {status ? `${status.database.images} img · ${status.database.sols} sols` : '—'}
          </dd>
        </div>
        <div>
          <dt className="label">NASA feed</dt>
          <dd className="mono">{status?.feed?.latest_sol != null ? `SOL ${formatSol(status.feed.latest_sol)}` : '—'}</dd>
        </div>
      </dl>

      <div className="topbar__pips" aria-label="System status">
        <StatusPip state={apiState} label="API" detail={state.status === 'error' ? state.error.message : undefined} />
        <StatusPip state={dbState} label="Data" detail={status ? `${status.database.images} images stored` : undefined} />
        <StatusPip
          state={feedState}
          label="Feed"
          detail={status?.feed ? `checked ${status.feed.checked_at}` : 'not checked yet'}
        />
      </div>
    </header>
  )
}
