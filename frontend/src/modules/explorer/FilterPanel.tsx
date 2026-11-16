import { useState, type ReactNode } from 'react'
import type { ImageFilters } from '../../api/client'
import type { CameraWithCount } from '../../api/types'
import { GROUP_LABELS } from '../mission-control/grouping'
import { hasFilters } from './explorerFilters'

interface FilterPanelProps {
  filters: ImageFilters
  cameras: CameraWithCount[]
  onChange: (filters: ImageFilters) => void
  children?: ReactNode
}

function toInt(value: string): number | undefined {
  if (value.trim() === '') return undefined
  const n = Number(value)
  return Number.isInteger(n) && n >= 0 ? n : undefined
}

/** Text inputs commit on blur/Enter so typing "2" does not immediately filter to sol 2. */
function CommitInput({
  label,
  value,
  onCommit,
  type = 'text',
  placeholder,
  inputMode,
}: {
  label: string
  value: string
  onCommit: (value: string) => void
  type?: 'text' | 'date'
  placeholder?: string
  inputMode?: 'numeric'
}) {
  const [draft, setDraft] = useState(value)
  const [committed, setCommitted] = useState(value)
  if (committed !== value) {
    // The filter changed from outside (e.g. "Clear all"): show the new value.
    setCommitted(value)
    setDraft(value)
  }
  const commit = () => {
    if (draft !== value) onCommit(draft)
  }
  return (
    <label className="xf__field">
      <span className="label">{label}</span>
      <input
        type={type}
        value={draft}
        placeholder={placeholder}
        inputMode={inputMode}
        onChange={(event) => {
          setDraft(event.target.value)
          if (type === 'date') onCommit(event.target.value)
        }}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') commit()
        }}
      />
    </label>
  )
}

export function FilterPanel({ filters, cameras, onChange, children }: FilterPanelProps) {
  const [showAll, setShowAll] = useState(false)
  const selected = new Set(filters.cameras ?? [])

  const byGroup = new Map<string, CameraWithCount[]>()
  for (const camera of cameras) {
    if (!showAll && camera.image_count === 0 && !selected.has(camera.instrument)) continue
    byGroup.set(camera.group, [...(byGroup.get(camera.group) ?? []), camera])
  }
  const groups = [...byGroup.entries()]

  const toggleCamera = (instrument: string) => {
    const next = new Set(selected)
    if (next.has(instrument)) next.delete(instrument)
    else next.add(instrument)
    onChange({ ...filters, cameras: [...next].sort() })
  }

  const singleSol = filters.sol !== undefined

  return (
    <aside className="xf" aria-label="Filters">
      <div className="xf__head">
        <h2 className="label">Filters</h2>
        {hasFilters(filters) && (
          <button type="button" className="xf__clear" onClick={() => onChange({})}>
            Clear all
          </button>
        )}
      </div>

      <div className="xf__section">
        <CommitInput
          label="Image id contains"
          value={filters.q ?? ''}
          placeholder="e.g. NCAM00518"
          onCommit={(value) => onChange({ ...filters, q: value.trim() || undefined })}
        />
      </div>

      <div className="xf__section">
        <h3 className="label">Sol</h3>
        {singleSol ? (
          <div className="xf__chip">
            <span className="mono">SOL {filters.sol}</span>
            <button type="button" onClick={() => onChange({ ...filters, sol: undefined })} aria-label="Remove sol filter">
              ×
            </button>
          </div>
        ) : (
          <div className="xf__pair">
            <CommitInput
              label="From"
              inputMode="numeric"
              value={filters.solMin?.toString() ?? ''}
              placeholder="0"
              onCommit={(value) => onChange({ ...filters, solMin: toInt(value) })}
            />
            <CommitInput
              label="To"
              inputMode="numeric"
              value={filters.solMax?.toString() ?? ''}
              placeholder="latest"
              onCommit={(value) => onChange({ ...filters, solMax: toInt(value) })}
            />
          </div>
        )}
      </div>

      <div className="xf__section">
        <h3 className="label">Earth date taken (UTC)</h3>
        <div className="xf__stack">
          <CommitInput label="From" type="date" value={filters.dateFrom ?? ''} onCommit={(v) => onChange({ ...filters, dateFrom: v || undefined })} />
          <CommitInput label="To" type="date" value={filters.dateTo ?? ''} onCommit={(v) => onChange({ ...filters, dateTo: v || undefined })} />
        </div>
      </div>

      <div className="xf__section">
        <div className="xf__subhead">
          <h3 className="label">Cameras</h3>
          <button type="button" className="xf__toggle" onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Only stored' : `All ${cameras.length}`}
          </button>
        </div>
        {groups.map(([group, list]) => (
          <fieldset key={group} className="xf__group">
            <legend className="xf__legend">{GROUP_LABELS[group as keyof typeof GROUP_LABELS] ?? group}</legend>
            {list.map((camera) => (
              <label key={camera.instrument} className="xf__check" title={camera.label}>
                <input type="checkbox" checked={selected.has(camera.instrument)} onChange={() => toggleCamera(camera.instrument)} />
                <span className="xf__name">{camera.instrument.replace(/_/g, ' ')}</span>
                <span className="xf__count mono">{camera.image_count}</span>
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      {children}
    </aside>
  )
}
