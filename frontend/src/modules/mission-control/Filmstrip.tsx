import { useEffect, useMemo, useRef } from 'react'
import type { ImageSummary } from '../../api/types'
import { Skeleton } from '../../design-system/primitives'
import { formatSol } from '../../lib/format'
import { groupBySol } from './grouping'

interface FilmstripProps {
  items: ImageSummary[]
  selectedId: string | null
  onSelect: (imageId: string) => void
  loading: boolean
  total: number | null
}

export function Filmstrip({ items, selectedId, onSelect, loading, total }: FilmstripProps) {
  const groups = useMemo(() => groupBySol(items), [items])
  const selectedRef = useRef<HTMLButtonElement | null>(null)

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })
  }, [selectedId])

  return (
    <section className="strip" aria-label="Recent observations">
      <header className="strip__header">
        <h2 className="label">Recent observations</h2>
        <span className="strip__meta mono">
          {total !== null ? `${items.length} of ${total} in local archive · ← → to step` : ''}
        </span>
      </header>
      <div className="strip__scroller">
        {loading
          ? Array.from({ length: 10 }, (_, i) => (
              <div className="strip__thumb strip__thumb--skeleton" key={i}>
                <Skeleton height={84} />
              </div>
            ))
          : groups.map((group) => (
              <div className="strip__group" key={group.sol} role="group" aria-label={`Sol ${group.sol}`}>
                <span className="strip__sol mono">SOL {formatSol(group.sol)}</span>
                <div className="strip__items">
                  {group.items.map((item) => {
                    const selected = item.image_id === selectedId
                    return (
                      <button
                        type="button"
                        key={item.image_id}
                        ref={selected ? selectedRef : undefined}
                        className={`strip__thumb${selected ? ' is-selected' : ''}`}
                        aria-pressed={selected}
                        onClick={() => onSelect(item.image_id)}
                        title={`${item.camera.label} · sol ${item.sol}${item.lmst ? ` · ${item.lmst} LMST` : ''}`}
                      >
                        <img src={item.thumb_url} alt={`${item.camera.instrument}, sol ${item.sol}`} loading="lazy" />
                        <span className="strip__cam mono">{item.camera.instrument.replace(/_/g, ' ')}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
      </div>
    </section>
  )
}
