import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ImageFilters } from '../../api/client'
import type { ImageSummary } from '../../api/types'
import { useApi } from '../../api/useApi'
import { ErrorState, SkeletonBlock } from '../../design-system/primitives'
import { formatSol } from '../../lib/format'
import { CompareView } from './CompareView'
import { filtersKey } from './explorerFilters'
import { Inspector } from './Inspector'
import { RelatedPanel } from './RelatedPanel'
import { FIT, type Size, type View } from './zoom'
import { ZoomViewer } from './ZoomViewer'

interface ImageDetailViewProps {
  imageId: string
  filters: ImageFilters
  dataVersion: number
  onBack: () => void
  onNavigate: (imageId: string) => void
  onDataChanged: () => void
}

type Rendition = 'large' | 'full_res'

function isTypingOrViewer(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return Boolean(target.closest('input, textarea, select, [contenteditable="true"], .zv__stage, [role="slider"]'))
}

export function ImageDetailView({ imageId, filters, dataVersion, onBack, onNavigate, onDataChanged }: ImageDetailViewProps) {
  const detail = useApi(`detail:${imageId}:${dataVersion}`, (signal) => api.image(imageId, signal))
  const neighbors = useApi(`neighbors:${imageId}:${filtersKey(filters)}:${dataVersion}`, (signal) =>
    api.neighbors(imageId, filters, signal),
  )
  const [view, setView] = useState<View>(FIT)
  const [rendition, setRendition] = useState<Rendition>('large')
  const [natural, setNatural] = useState<Size | null>(null)
  const [compare, setCompare] = useState<{ image: ImageSummary; stereo: boolean } | null>(null)

  const previous = neighbors.state.data?.previous ?? null
  const next = neighbors.state.data?.next ?? null

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingOrViewer(event.target) || event.altKey || event.ctrlKey || event.metaKey) return
      if (event.key === 'ArrowLeft' && previous) onNavigate(previous.image_id)
      else if (event.key === 'ArrowRight' && next) onNavigate(next.image_id)
      else if (event.key === 'Escape') {
        if (compare) setCompare(null)
        else onBack()
      } else return
      event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [previous, next, compare, onNavigate, onBack])

  if (detail.state.status === 'error') {
    return (
      <div className="xd">
        <button type="button" className="ds-button" onClick={onBack}>
          ← Back to results
        </button>
        <ErrorState title="Image unavailable" message={detail.state.error.message} onRetry={detail.retry} />
      </div>
    )
  }

  const data = detail.state.data
  const nb = neighbors.state.data
  const src = data ? `/api/images/${encodeURIComponent(data.image_id)}/file/${rendition}` : null

  return (
    <div className={`xd${compare ? ' is-comparing' : ''}`}>
      <header className="xd__bar">
        <button type="button" className="ds-button" onClick={onBack} title="Back to results (Esc)">
          ← Results
        </button>
        <div className="xd__title">
          {data ? (
            <>
              <span className="mono xd__sol">SOL {formatSol(data.sol)}</span>
              <span className="xd__cam">{data.camera.label}</span>
            </>
          ) : (
            <span className="xd__cam">Loading…</span>
          )}
        </div>
        <Link className="xd__perception" to={`/perception/${encodeURIComponent(imageId)}`}>
          Analyze in Perception
        </Link>
        <div className="xd__nav">
          <span className="mono xd__pos">
            {nb?.position ? `${nb.position} / ${nb.total}` : nb ? `outside filter · ${nb.total}` : ''}
          </span>
          <button type="button" className="ds-button" disabled={!previous} onClick={() => previous && onNavigate(previous.image_id)} title="Earlier image (←)">
            ‹ Earlier
          </button>
          <button type="button" className="ds-button" disabled={!next} onClick={() => next && onNavigate(next.image_id)} title="Later image (→)">
            Later ›
          </button>
        </div>
      </header>

      <div className="xd__body">
        <div className="xd__main">
          {compare && data ? (
            <CompareView a={data} b={compare.image} stereo={compare.stereo} onClose={() => setCompare(null)} />
          ) : src ? (
            <>
              <ZoomViewer
                layers={[{ src, alt: `${data!.camera.label}, sol ${data!.sol}` }]}
                view={view}
                onViewChange={setView}
                label={data!.camera.label}
                onNaturalSize={setNatural}
              />
              <div className="xd__rendition">
                <div role="radiogroup" aria-label="Rendition">
                  {(['large', 'full_res'] as const).map((r) => (
                    <button key={r} type="button" role="radio" aria-checked={rendition === r} className={rendition === r ? 'is-active' : ''} onClick={() => setRendition(r)}>
                      {r === 'large' ? 'Preview JPEG' : 'Full resolution PNG'}
                    </button>
                  ))}
                </div>
                <span className="mono">
                  {natural ? `showing ${natural.width} × ${natural.height} px` : 'loading…'}
                  {rendition === 'full_res' && !data!.local_files.full_res ? ' · fetched from NASA on first view' : ''}
                </span>
              </div>
            </>
          ) : (
            <SkeletonBlock lines={8} />
          )}
        </div>
        <aside className="xd__side" aria-label="Metadata">
          {data ? <Inspector detail={data} /> : <SkeletonBlock lines={14} />}
        </aside>
        <div className="xd__related">
          <RelatedPanel
            imageId={imageId}
            dataVersion={dataVersion}
            onOpen={onNavigate}
            onCompare={(image, stereo) => setCompare({ image, stereo })}
            onDataChanged={onDataChanged}
          />
        </div>
      </div>
    </div>
  )
}
