import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, type ImageFilters } from '../../api/client'
import type { ImageSummary } from '../../api/types'
import { CommandHint, EmptyState, ErrorState, Skeleton } from '../../design-system/primitives'
import { shortInstrument } from '../../lib/cameras'
import { formatSol } from '../../lib/format'
import { groupBySol } from '../mission-control/grouping'
import { describeFilters, filtersKey, hasFilters } from './explorerFilters'

export const PAGE_SIZE = 60

interface ImageGridProps {
  filters: ImageFilters
  dataVersion: number
  onOpen: (imageId: string) => void
  onClearFilters: () => void
}

type GridState =
  | { status: 'loading' }
  | { status: 'error'; error: ApiError }
  | { status: 'ready'; items: ImageSummary[]; total: number; loadingMore: boolean; moreError: ApiError | null }

const asApiError = (error: unknown) => (error instanceof ApiError ? error : new ApiError(0, 'unexpected', String(error)))

export function ImageGrid({ filters, dataVersion, onOpen, onClearFilters }: ImageGridProps) {
  const key = `${filtersKey(filters)}|${dataVersion}`
  const [state, setState] = useState<GridState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })
    api.images({ ...filters, limit: PAGE_SIZE, offset: 0 }, controller.signal).then(
      (page) => setState({ status: 'ready', items: page.items, total: page.total, loadingMore: false, moreError: null }),
      (error: unknown) => {
        if (!controller.signal.aborted) setState({ status: 'error', error: asApiError(error) })
      },
    )
    return () => controller.abort()
    // `key` captures filters + data version
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt])

  const loadMore = () => {
    if (state.status !== 'ready' || state.loadingMore) return
    setState({ ...state, loadingMore: true, moreError: null })
    api.images({ ...filters, limit: PAGE_SIZE, offset: state.items.length }).then(
      (page) =>
        setState((current) =>
          current.status === 'ready'
            ? { ...current, items: [...current.items, ...page.items], total: page.total, loadingMore: false }
            : current,
        ),
      (error: unknown) =>
        setState((current) => (current.status === 'ready' ? { ...current, loadingMore: false, moreError: asApiError(error) } : current)),
    )
  }

  const groups = useMemo(() => (state.status === 'ready' ? groupBySol(state.items) : []), [state])

  if (state.status === 'loading') {
    return (
      <div className="xg__grid" aria-busy="true">
        {Array.from({ length: 18 }, (_, i) => (
          <Skeleton key={i} height={132} />
        ))}
      </div>
    )
  }
  if (state.status === 'error') {
    return <ErrorState title="Could not load images" message={state.error.message} onRetry={() => setAttempt((n) => n + 1)} />
  }
  if (state.items.length === 0) {
    return (
      <EmptyState title={hasFilters(filters) ? 'No stored images match these filters' : 'The local archive is empty'}>
        {hasFilters(filters) ? (
          <>
            <p>Filters: {describeFilters(filters)}. Clear some filters, or download matching data from NASA with “Add data from NASA”.</p>
            <button type="button" className="ds-button" onClick={onClearFilters}>
              Clear filters
            </button>
          </>
        ) : (
          <CommandHint command="cd backend; uv run mars-ingest seed" />
        )}
      </EmptyState>
    )
  }

  return (
    <div className="xg">
      <p className="xg__summary mono" aria-live="polite">
        {state.items.length} of {state.total} · {describeFilters(filters)}
      </p>
      {groups.map((group) => (
        <section key={group.sol} className="xg__sol" aria-label={`Sol ${group.sol}`}>
          <h3 className="xg__solhead">
            <span className="mono">SOL {formatSol(group.sol)}</span>
            <span className="xg__solcount">{group.items.length} shown</span>
          </h3>
          <div className="xg__grid">
            {group.items.map((item) => (
              <button
                key={item.image_id}
                type="button"
                className="xg__card"
                onClick={() => onOpen(item.image_id)}
                title={`${item.camera.label} · ${item.image_id}`}
              >
                <span className="xg__thumb">
                  <img src={item.thumb_url} alt={`${item.camera.instrument}, sol ${item.sol}`} loading="lazy" />
                </span>
                <span className="xg__meta">
                  <span className="xg__cam mono">{shortInstrument(item.camera.instrument)}</span>
                  <span className="xg__time mono">{item.lmst ?? '—'}</span>
                </span>
              </button>
            ))}
          </div>
        </section>
      ))}
      {state.items.length < state.total && (
        <div className="xg__more">
          <button type="button" className="ds-button" onClick={loadMore} disabled={state.loadingMore}>
            {state.loadingMore ? 'Loading…' : `Load ${Math.min(PAGE_SIZE, state.total - state.items.length)} more`}
          </button>
          {state.moreError && <span className="xg__error">{state.moreError.message}</span>}
        </div>
      )}
    </div>
  )
}
