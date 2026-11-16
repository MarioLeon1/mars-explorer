import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import { useApi } from '../../api/useApi'
import { CommandHint, EmptyState, ErrorState } from '../../design-system/primitives'
import { ArchivePanel } from './ArchivePanel'
import { Filmstrip } from './Filmstrip'
import { ImageViewport } from './ImageViewport'
import { ObservationPanel } from './ObservationPanel'
import { RoverStatusPanel } from './RoverStatusPanel'
import { TraversePanel } from './TraversePanel'
import './mission-control.css'

const RECENT_LIMIT = 60

function isTypingTarget(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))
}

export function MissionControl() {
  const images = useApi('recent-images', (signal) => api.images({ limit: RECENT_LIMIT }, signal))
  const items = useMemo(() => images.state.data?.items ?? [], [images.state.data])
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selectedIndex = Math.max(
    0,
    items.findIndex((item) => item.image_id === selectedId),
  )
  const selected = items[selectedIndex] ?? null

  const detail = useApi(selected ? `image:${selected.image_id}` : null, (signal) =>
    api.image(selected?.image_id ?? '', signal),
  )

  const step = useCallback(
    (delta: number) => {
      if (items.length === 0) return
      const next = Math.min(items.length - 1, Math.max(0, selectedIndex + delta))
      setSelectedId(items[next]?.image_id ?? null)
    },
    [items, selectedIndex],
  )

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target) || event.altKey || event.ctrlKey || event.metaKey) return
      if (event.key === 'ArrowRight') step(1)
      else if (event.key === 'ArrowLeft') step(-1)
      else return
      event.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [step])

  if (images.state.status === 'error') {
    const unreachable = images.state.error.isUnreachable
    return (
      <div className="mc-blocking">
        <ErrorState
          title={unreachable ? 'The Mars Explorer API is not reachable' : 'Could not load observations'}
          message={
            unreachable
              ? 'Start the backend in another terminal, then retry. Mission Control needs it to read the local archive.'
              : images.state.error.message
          }
          onRetry={images.retry}
        >
          {unreachable && <CommandHint command="cd backend; uv run uvicorn mars_explorer.api.app:app --port 8000" />}
        </ErrorState>
      </div>
    )
  }

  if (images.state.status === 'success' && items.length === 0) {
    return (
      <div className="mc-blocking">
        <EmptyState title="No observations in the local archive yet">
          <p>Download a curated set of real Perseverance images (about 13 MB) and the rover localizations:</p>
          <CommandHint command="cd backend; uv run mars-ingest seed" />
          <p>Then reload this page.</p>
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="mc">
      <div className="mc__left">
        <ObservationPanel summary={selected} detail={detail.state} />
        <ArchivePanel />
      </div>
      <ImageViewport
        summary={selected}
        detail={detail.state.data ?? null}
        loading={images.state.status === 'loading'}
        position={items.length ? { index: selectedIndex, total: items.length } : null}
        onStep={step}
      />
      <Filmstrip
        items={items}
        selectedId={selected?.image_id ?? null}
        onSelect={setSelectedId}
        loading={images.state.status === 'loading'}
        total={images.state.data?.total ?? null}
      />
      <div className="mc__right">
        <RoverStatusPanel />
        <TraversePanel />
      </div>
    </div>
  )
}
