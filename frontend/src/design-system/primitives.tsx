import type { ReactNode } from 'react'

export type PipState = 'ok' | 'warn' | 'error' | 'idle'

export function StatusPip({ state, label, detail }: { state: PipState; label: string; detail?: string }) {
  return (
    <span className="ds-pip" title={detail ? `${label}: ${detail}` : label}>
      <span className={`ds-pip__dot ds-pip__dot--${state}`} aria-hidden="true" />
      <span className="ds-pip__label">{label}</span>
      <span className="visually-hidden">{` ${state}${detail ? `, ${detail}` : ''}`}</span>
    </span>
  )
}

export interface DataItem {
  label: string
  value: ReactNode
  /** Render the value in the monospace numeric face (default true). */
  mono?: boolean
  hint?: string
}

/** Two-column label/value list; values default to tabular monospace. */
export function DataList({ items, columns = 1 }: { items: DataItem[]; columns?: 1 | 2 }) {
  return (
    <dl className={`ds-data ds-data--cols-${columns}`}>
      {items.map((item) => (
        <div className="ds-data__row" key={item.label} title={item.hint}>
          <dt className="label">{item.label}</dt>
          <dd className={item.mono === false ? '' : 'mono'}>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Skeleton({ height = 12, width = '100%' }: { height?: number; width?: number | string }) {
  return <span className="ds-skeleton" style={{ height, width }} aria-hidden="true" />
}

export function SkeletonBlock({ lines = 4 }: { lines?: number }) {
  return (
    <div className="ds-skeleton-block" role="status" aria-label="Loading">
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} width={`${90 - ((i * 17) % 40)}%`} />
      ))}
    </div>
  )
}

export function ErrorState({
  title,
  message,
  onRetry,
  children,
}: {
  title: string
  message: string
  onRetry?: () => void
  children?: ReactNode
}) {
  return (
    <div className="ds-state ds-state--error" role="alert">
      <p className="ds-state__title">{title}</p>
      <p className="ds-state__message">{message}</p>
      {children}
      {onRetry && (
        <button type="button" className="ds-button" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="ds-state">
      <p className="ds-state__title">{title}</p>
      {children}
    </div>
  )
}

export function CommandHint({ command }: { command: string }) {
  return <code className="ds-command mono">{command}</code>
}
