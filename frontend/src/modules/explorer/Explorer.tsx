import { useCallback, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, type ImageFilters } from '../../api/client'
import { useApi } from '../../api/useApi'
import { useSystemStatus } from '../../app/systemStatus'
import { FilterPanel } from './FilterPanel'
import { ImageDetailView } from './ImageDetailView'
import { ImageGrid } from './ImageGrid'
import { IngestPanel } from './IngestPanel'
import { readFilters, writeFilters } from './explorerFilters'
import { SolTimeline } from './SolTimeline'
import './explorer.css'

/**
 * Explorer: `/explorer?…filters` shows the grid, `/explorer/:imageId?…filters` the detail view.
 * Filters live in the URL so views are shareable and the browser Back button works.
 */
export function Explorer() {
  const { imageId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const filters = useMemo(() => readFilters(searchParams), [searchParams])
  const query = searchParams.toString()

  const [dataVersion, setDataVersion] = useState(0)
  const { retry: refreshStatus, state: status } = useSystemStatus()
  const onDataChanged = useCallback(() => {
    setDataVersion((v) => v + 1)
    refreshStatus()
  }, [refreshStatus])

  const cameras = useApi(`cameras:${dataVersion}`, api.cameras)
  const sols = useApi(`sols:${dataVersion}`, api.sols)

  const setFilters = (next: ImageFilters) => setSearchParams(writeFilters(next))
  const open = useCallback(
    (id: string) => navigate({ pathname: `/explorer/${encodeURIComponent(id)}`, search: query }),
    [navigate, query],
  )
  const back = useCallback(() => navigate({ pathname: '/explorer', search: query }), [navigate, query])

  return (
    <div className="xp">
      <FilterPanel filters={filters} cameras={cameras.state.data ?? []} onChange={setFilters}>
        <IngestPanel defaultSol={filters.sol} onDataChanged={onDataChanged} />
      </FilterPanel>
      <div className="xp__main">
        {imageId ? (
          <ImageDetailView
            key={imageId}
            imageId={imageId}
            filters={filters}
            dataVersion={dataVersion}
            onBack={back}
            onNavigate={open}
            onDataChanged={onDataChanged}
          />
        ) : (
          <>
            <SolTimeline
              sols={sols.state.data ?? []}
              latestSol={status.data?.feed?.latest_sol ?? null}
              selectedSol={filters.sol}
              onSelect={(sol) => setFilters({ ...filters, sol, solMin: undefined, solMax: undefined })}
            />
            <ImageGrid filters={filters} dataVersion={dataVersion} onOpen={open} onClearFilters={() => setFilters({})} />
          </>
        )}
      </div>
    </div>
  )
}
