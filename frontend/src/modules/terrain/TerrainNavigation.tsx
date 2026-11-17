import { useEffect, useMemo, useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { CostModel, EN, MapRequest, Plan, PlannerName, TerrainMap } from '../../api/types'
import { useApi } from '../../api/useApi'
import { Panel } from '../../design-system/Panel'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { CommandHint, EmptyState, ErrorState, SkeletonBlock } from '../../design-system/primitives'
import { formatNumber } from '../../lib/format'
import { FIT, type View } from '../explorer/zoom'
import { ZoomViewer } from '../explorer/ZoomViewer'
import '../explorer/explorer.css'
import '../perception/perception.css'
import { ElevationProfile, type ProfileSeries } from './ElevationProfile'
import { DEFAULT_COST_MODEL, fromFraction, PLANNER_ORDER, requestKey, ROUTE_STYLE, toFraction } from './geometry'
import { OverviewMap } from './OverviewMap'
import { PlannerControls } from './PlannerControls'
import { RouteResults } from './RouteResults'
import './terrain.css'

type OverlayLayer = 'none' | 'slope' | 'roughness' | 'risk'
type PickMode = 'start' | 'goal' | null

const SIZES = [400, 800, 1500, 3000]
const message = (error: unknown) => (error instanceof ApiError ? error.message : String(error))

export function TerrainNavigation() {
  const status = useApi('terrain-status', api.terrainStatus)
  const drives = useApi(status.state.data?.available ? 'terrain-drives' : null, (signal) => api.drives(10, signal))

  const [mapRequest, setMapRequest] = useState<MapRequest | null>(null)
  const [loaded, setLoaded] = useState<{ key: string; map: TerrainMap } | null>(null)
  const [failed, setFailed] = useState<{ key: string; message: string } | null>(null)
  const [size, setSize] = useState(800)
  const [driveRange, setDriveRange] = useState<[number, number] | null>(null)
  const [costModel, setCostModel] = useState<CostModel>(DEFAULT_COST_MODEL)
  const [planners, setPlanners] = useState<PlannerName[]>(PLANNER_ORDER)
  const [seed, setSeed] = useState(42)
  const [iterations, setIterations] = useState(3000)
  const [start, setStart] = useState<EN | null>(null)
  const [goal, setGoal] = useState<EN | null>(null)
  const [pick, setPick] = useState<PickMode>(null)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [planning, setPlanning] = useState(false)
  const [planError, setPlanError] = useState<string | null>(null)
  const [overlay, setOverlay] = useState<OverlayLayer>('risk')
  const [opacity, setOpacity] = useState(0.7)
  const [view, setView] = useState<View>(FIT)

  const driveList = useMemo(() => drives.state.data ?? [], [drives.state.data])

  // Region: explicit request, or by default the end of the latest real drive (where the rover is).
  const activeRequest = useMemo<MapRequest | null>(() => {
    if (mapRequest) return mapRequest
    const last = driveList[driveList.length - 1]
    const point = last?.points[last.points.length - 1]
    return point ? { center: { e: point[0], n: point[1] }, size_m: 800, cost_model: DEFAULT_COST_MODEL } : null
  }, [mapRequest, driveList])
  const key = requestKey(activeRequest)

  // Build (or fetch the cached) map for the active request. Loading/error are derived from keys.
  useEffect(() => {
    if (!key || !activeRequest || loaded?.key === key) return
    let cancelled = false
    api.terrainMap(activeRequest).then(
      (map) => {
        if (cancelled) return
        setLoaded({ key, map })
        setView(FIT)
      },
      (error: unknown) => !cancelled && setFailed({ key, message: message(error) }),
    )
    return () => {
      cancelled = true
    }
  }, [key, activeRequest, loaded?.key])
  const terrainMap = loaded?.map ?? null
  const mapError = failed?.key === key ? failed.message : null
  const mapLoading = key !== null && loaded?.key !== key && !mapError

  const moveTo = (center: EN, newSize = size) => {
    setDriveRange(null)
    setPlan(null)
    setStart(null)
    setGoal(null)
    setMapRequest({ center, size_m: newSize, cost_model: costModel })
  }

  const loadDrives = (range: [number, number]) => {
    setDriveRange(range)
    setPlan(null)
    setStart(null)
    setGoal(null)
    setMapRequest({ drives: range, margin_m: 120, cost_model: costModel })
  }

  const runPlan = async () => {
    if (!activeRequest) return
    const request = { ...activeRequest, cost_model: costModel }
    setPlanning(true)
    setPlanError(null)
    try {
      const result = await api.plan({
        map: request,
        start: start ?? undefined,
        goal: goal ?? undefined,
        planners,
        rrt_seed: seed,
        rrt_iterations: iterations,
      })
      setPlan(result)
      setLoaded({ key: requestKey(request)!, map: result.map }) // cost model may have changed layers
      setMapRequest(request)
      setStart(result.start)
      setGoal(result.goal)
    } catch (error) {
      setPlanError(message(error))
    } finally {
      setPlanning(false)
    }
  }

  if (status.state.status === 'loading') return <SkeletonBlock lines={10} />
  if (status.state.status === 'error') {
    return <ErrorState title="Terrain service unavailable" message={status.state.error.message} onRetry={status.retry} />
  }
  const info = status.state.data
  if (!info.available) {
    return (
      <div className="mc-blocking">
        <EmptyState title="The orbital elevation model is not downloaded yet">
          <p>Download the real 1 m/pixel DEM of the traverse area (about 325 MB, from the NASA PDS):</p>
          <CommandHint command={info.how_to_get ?? 'cd backend; uv run mars-terrain fetch'} />
          <p>Then reload this page.</p>
        </EmptyState>
      </div>
    )
  }

  const extent = terrainMap?.extent ?? null
  const canPlan = Boolean(terrainMap && (driveRange || (start && goal)))
  const hillshade = terrainMap?.layers.find((l) => l.name === 'hillshade')
  const overlayLayer = overlay === 'none' ? null : terrainMap?.layers.find((l) => l.name === overlay)
  const routes = plan ? [...plan.routes.filter((r) => r.found), ...(plan.actual ? [plan.actual] : [])] : []
  const profileSeries: ProfileSeries[] = routes
    .filter((r) => r.metrics?.profile.length)
    .map((r) => ({ key: r.planner, label: ROUTE_STYLE[r.planner].label, color: ROUTE_STYLE[r.planner].color, dash: ROUTE_STYLE[r.planner].dash, profile: r.metrics!.profile }))

  return (
    <div className="tn">
      <aside className="tn-left" aria-label="Region">
        <Panel title="Jezero — orbital DEM" meta={<ProvenanceBadge provenance="real_observation" credit="PDS PLACES" />}>
          <OverviewMap extent={info.extent} drives={driveList} roi={extent} onPick={(c) => moveTo(c)} />
          <p className="tn-muted">
            Click to move the working map. Lines: the real traverse ({driveList.length} drives). Dot: latest position.
          </p>
          <div className="ph__presets" role="radiogroup" aria-label="Map size">
            <span className="label">Size</span>
            {SIZES.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={size === s}
                className={size === s ? 'is-active' : ''}
                onClick={() => {
                  setSize(s)
                  if (terrainMap) moveTo(terrainMap.center, s)
                }}
              >
                {s >= 1000 ? `${s / 1000} km` : `${s} m`}
              </button>
            ))}
          </div>
          {info.validation && (
            <p className="tn-muted mono">
              Georeferencing check: {info.validation.compared} real localizations, median elevation offset{' '}
              {info.validation.median_offset_m} m (95 % within {info.validation.p95_abs_offset_m} m).
            </p>
          )}
        </Panel>

        <Panel title="Replan a real drive">
          <p className="tn-muted">Start and goal = the ends of real drives; the rover’s actual path is compared with each plan.</p>
          {/* keyed by count: defaults (latest drives) are computed once the list has arrived */}
          <DriveRangePicker key={driveList.length} drives={driveList} value={driveRange} onLoad={loadDrives} />
        </Panel>
      </aside>

      <section className="tn-center" aria-label="Working map">
        <div className="tn-toolbar">
          <div className="pw__tabs" role="radiogroup" aria-label="Click mode">
            {(['start', 'goal'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                role="radio"
                aria-checked={pick === mode}
                className={pick === mode ? 'is-active' : ''}
                onClick={() => setPick(pick === mode ? null : mode)}
              >
                {mode === 'start' ? 'Set start (A)' : 'Set goal (B)'}
              </button>
            ))}
          </div>
          <div className="pw__tabs" role="radiogroup" aria-label="Overlay">
            {(['none', 'risk', 'slope', 'roughness'] as const).map((name) => (
              <button key={name} type="button" role="radio" aria-checked={overlay === name} className={overlay === name ? 'is-active' : ''} onClick={() => setOverlay(name)}>
                {name === 'none' ? 'Relief' : name[0]!.toUpperCase() + name.slice(1)}
              </button>
            ))}
          </div>
          <label className="pw__opacity">
            <span className="label">Overlay</span>
            <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} aria-label="Overlay opacity" />
          </label>
        </div>

        <div className="tn-map">
          {mapError ? (
            <ErrorState title="Could not build this map" message={mapError} />
          ) : terrainMap && hillshade && extent ? (
            <ZoomViewer
              layers={[
                { src: hillshade.url, alt: 'Shaded relief of the orbital DEM' },
                ...(overlayLayer ? [{ src: overlayLayer.url, alt: overlayLayer.label, opacity }] : []),
              ]}
              view={view}
              onViewChange={setView}
              label="Terrain map"
              clickMode={pick !== null}
              onImageClick={
                pick
                  ? (x, y) => {
                      const point = fromFraction(extent, x, y)
                      if (pick === 'start') {
                        setStart(point)
                        setPick('goal')
                      } else {
                        setGoal(point)
                        setPick(null)
                      }
                      setDriveRange(null)
                      if (activeRequest?.drives && terrainMap) {
                        setMapRequest({ center: terrainMap.center, size_m: terrainMap.size_m, cost_model: costModel })
                      }
                    }
                  : undefined
              }
              overlay={(natural, scale) => {
                const px = (e: number, n: number) => {
                  const f = toFraction(extent, e, n)
                  return `${(f.x * natural.width).toFixed(1)},${(f.y * natural.height).toFixed(1)}`
                }
                const marker = (p: EN, label: string) => {
                  const f = toFraction(extent, p.e, p.n)
                  const r = 9 / scale
                  return (
                    <g className="tn-marker">
                      <circle cx={f.x * natural.width} cy={f.y * natural.height} r={r} />
                      <text x={f.x * natural.width} y={f.y * natural.height + r * 0.38} fontSize={r * 1.15} textAnchor="middle">
                        {label}
                      </text>
                    </g>
                  )
                }
                return (
                  <>
                    {terrainMap.drives_in_view.map((d) => (
                      <polyline key={d.index} className="tn-drive" points={d.points.map(([e, n]) => px(e, n)).join(' ')} />
                    ))}
                    {routes.map((r) => (
                      <g key={r.planner}>
                        <polyline className="tn-route-halo" points={r.points.map(([e, n]) => px(e, n)).join(' ')} />
                        <polyline
                          className="tn-route"
                          stroke={ROUTE_STYLE[r.planner].color}
                          strokeDasharray={ROUTE_STYLE[r.planner].dash}
                          points={r.points.map(([e, n]) => px(e, n)).join(' ')}
                        />
                      </g>
                    ))}
                    {start && marker(start, 'A')}
                    {goal && marker(goal, 'B')}
                  </>
                )
              }}
            >
              {(mapLoading || planning) && <span className="pw__running mono">{planning ? 'planning…' : 'loading map…'}</span>}
            </ZoomViewer>
          ) : (
            <SkeletonBlock lines={12} />
          )}
        </div>

        {terrainMap && (
          <div className="tn-mapinfo">
            {overlayLayer && (
              <ul className="tn-legend" aria-label={`${overlayLayer.label} legend`}>
                {overlayLayer.legend.map((item) => (
                  <li key={item.label}>
                    <i style={{ background: item.color }} aria-hidden="true" /> {item.label}
                  </li>
                ))}
              </ul>
            )}
            <span className="mono tn-muted">
              {terrainMap.size_m} m · planning cells {terrainMap.cell_m} m · slope p95 {terrainMap.stats.slope_p95_deg}° · impassable{' '}
              {formatNumber((terrainMap.stats.risk_fraction.impassable ?? 0) * 100, 1)} %
            </span>
            <ProvenanceBadge provenance="derived" credit="slope · risk" />
          </div>
        )}
        {routes.length > 0 && <ElevationProfile series={profileSeries} />}
      </section>

      <aside className="tn-right" aria-label="Planner">
        <Panel title="Route planner" scroll>
          {!canPlan && !planning && (
            <p className="tn-hint">
              {driveRange ? '' : 'Pick a start (A) and goal (B) on the map, or load a real drive on the left.'}
            </p>
          )}
          <PlannerControls
            costModel={costModel}
            onCostModel={setCostModel}
            planners={planners}
            onPlanners={setPlanners}
            seed={seed}
            onSeed={setSeed}
            iterations={iterations}
            onIterations={setIterations}
            running={planning}
            canRun={canPlan}
            onRun={() => void runPlan()}
          />
          {planError && (
            <p className="xi__error" role="alert">
              {planError}
            </p>
          )}
          {plan && <RouteResults plan={plan} />}
          {terrainMap && (
            <details className="tn-details">
              <summary>Assumptions and limitations</summary>
              <ul className="rp__limits">
                {[...terrainMap.assumptions, ...terrainMap.limitations].map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </details>
          )}
        </Panel>
      </aside>
    </div>
  )
}

function DriveRangePicker({
  drives,
  value,
  onLoad,
}: {
  drives: { index: number; sol: number; length_m: number | null }[]
  value: [number, number] | null
  onLoad: (range: [number, number]) => void
}) {
  const fallback = Math.max(0, drives.length - 6)
  const [first, setFirst] = useState(value?.[0] ?? fallback)
  const [last, setLast] = useState(value?.[1] ?? Math.max(0, drives.length - 1))
  const span = drives.slice(Math.min(first, last), Math.max(first, last) + 1)
  const total = span.reduce((sum, d) => sum + (d.length_m ?? 0), 0)
  const label = (d: { index: number; sol: number; length_m: number | null }) => `sol ${d.sol} · ${formatNumber(d.length_m ?? 0, 0)} m`
  if (drives.length === 0) return <p className="tn-muted">No drive paths ingested (run: uv run mars-ingest waypoints).</p>
  return (
    <div className="tn-drives">
      <label className="xf__field">
        <span className="label">From drive</span>
        <select value={first} onChange={(e) => setFirst(Number(e.target.value))}>
          {drives.map((d) => (
            <option key={d.index} value={d.index}>
              #{d.index} · {label(d)}
            </option>
          ))}
        </select>
      </label>
      <label className="xf__field">
        <span className="label">To drive</span>
        <select value={last} onChange={(e) => setLast(Number(e.target.value))}>
          {drives.map((d) => (
            <option key={d.index} value={d.index}>
              #{d.index} · {label(d)}
            </option>
          ))}
        </select>
      </label>
      <p className="tn-muted mono">
        {span.length} drive{span.length === 1 ? '' : 's'} · {formatNumber(total, 0)} m driven
      </p>
      <button type="button" className="ds-button" disabled={last < first} onClick={() => onLoad([first, last])}>
        Load these drives
      </button>
    </div>
  )
}
