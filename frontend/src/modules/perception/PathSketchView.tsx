import { useState } from 'react'
import { api, ApiError } from '../../api/client'
import type { FracPoint, ImageDetail, PathSketch, SketchDetector } from '../../api/types'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { DataList } from '../../design-system/primitives'
import { formatNumber } from '../../lib/format'
import { FIT, type View } from '../explorer/zoom'
import { ZoomViewer } from '../explorer/ZoomViewer'

type Pick = 'start' | 'goal' | null

const message = (error: unknown) => (error instanceof ApiError ? error.message : String(error))

/**
 * Image-space path sketch: rock candidates become obstacles and a deterministic planner draws
 * a path around them on the image. An illustration of hazard avoidance — never a real route.
 */
export function PathSketchView({ image }: { image: ImageDetail }) {
  const [view, setView] = useState<View>(FIT)
  const [start, setStart] = useState<FracPoint | null>(null)
  const [goal, setGoal] = useState<FracPoint | null>(null)
  const [pick, setPick] = useState<Pick>('goal')
  const [detector, setDetector] = useState<SketchDetector>('blobs')
  const [clearance, setClearance] = useState(1.6)
  const [roughness, setRoughness] = useState(2)
  const [autoHorizon, setAutoHorizon] = useState(true)
  const [horizon, setHorizon] = useState(0.3)
  const [showCost, setShowCost] = useState(true)
  const [showObstacles, setShowObstacles] = useState(true)
  const [result, setResult] = useState<PathSketch | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const plan = async (target: FracPoint | null = goal, origin: FracPoint | null = start) => {
    if (!target) return
    setRunning(true)
    setError(null)
    try {
      const sketch = await api.pathSketch({
        image_id: image.image_id,
        goal: target,
        ...(origin ? { start: origin } : {}),
        detector,
        clearance,
        roughness_weight: roughness,
        horizon: autoHorizon ? null : horizon,
      })
      setResult(sketch)
      if (sketch.horizon_auto) setHorizon(sketch.horizon)
    } catch (err) {
      setError(message(err))
    } finally {
      setRunning(false)
    }
  }

  const onImageClick = (x: number, y: number) => {
    const point = { x, y }
    if (pick === 'start') {
      setStart(point)
      setPick('goal')
      if (goal) void plan(goal, point)
    } else if (pick === 'goal') {
      setGoal(point)
      setPick(null)
      void plan(point, start)
    }
  }

  const m = result?.metrics

  return (
    <div className="pw__body ps">
      <div className="pw__viewer">
        <ZoomViewer
          layers={[{ src: image.preview_url, alt: `${image.camera.label}, sol ${image.sol}` }]}
          view={view}
          onViewChange={setView}
          label={image.camera.label}
          clickMode={pick !== null}
          onImageClick={pick ? onImageClick : undefined}
          overlay={(natural, scale) => {
            const sx = result ? natural.width / result.width : 1
            const sy = result ? natural.height / result.height : 1
            const marker = 9 / scale
            const horizonY = autoHorizon ? (result?.horizon ?? null) : horizon
            const startPt = result ? [result.start[0] * sx, result.start[1] * sy] : start ? [start.x * natural.width, start.y * natural.height] : null
            const goalPt = result ? [result.goal[0] * sx, result.goal[1] * sy] : goal ? [goal.x * natural.width, goal.y * natural.height] : null
            return (
              <>
                {result && showCost && (
                  <image
                    href={result.cost_layer}
                    width={natural.width}
                    height={natural.height}
                    preserveAspectRatio="none"
                    className="ps__cost"
                  />
                )}
                {horizonY !== null && (
                  <line className="ps__horizon" x1={0} x2={natural.width} y1={horizonY * natural.height} y2={horizonY * natural.height} />
                )}
                {result &&
                  showObstacles &&
                  result.obstacles.map((o, i) => (
                    <g key={i}>
                      <circle className="ps__obstacle" cx={o.x * sx} cy={o.y * sy} r={Math.max(o.r * sx, 2 / scale)} />
                      <circle className="ps__inflated" cx={o.x * sx} cy={o.y * sy} r={o.r * sx * clearance} />
                    </g>
                  ))}
                {startPt && goalPt && <line className="ps__straight" x1={startPt[0]} y1={startPt[1]} x2={goalPt[0]} y2={goalPt[1]} />}
                {result?.found && (
                  <polyline className="ps__path" points={result.path.map(([x, y]) => `${x * sx},${y * sy}`).join(' ')} />
                )}
                {startPt && (
                  <g className="ps__marker">
                    <circle cx={startPt[0]} cy={startPt[1]} r={marker} />
                    <text x={startPt[0]} y={startPt[1]} fontSize={marker * 1.3} dy="0.35em">
                      A
                    </text>
                  </g>
                )}
                {goalPt && (
                  <g className="ps__marker ps__marker--goal">
                    <circle cx={goalPt[0]} cy={goalPt[1]} r={marker} />
                    <text x={goalPt[0]} y={goalPt[1]} fontSize={marker * 1.3} dy="0.35em">
                      B
                    </text>
                  </g>
                )}
              </>
            )
          }}
        >
          <span className="ps__stamp">IMAGE-SPACE SKETCH · not a drivable route</span>
          {running && <span className="pw__running mono">planning…</span>}
        </ZoomViewer>
        <div className="pw__layers" aria-label="Layers">
          <span className="label">Show</span>
          <label className="pf__bool">
            <input type="checkbox" checked={showCost} onChange={(e) => setShowCost(e.target.checked)} />
            <span>Cost map</span>
          </label>
          <label className="pf__bool">
            <input type="checkbox" checked={showObstacles} onChange={(e) => setShowObstacles(e.target.checked)} />
            <span>Obstacles{m ? ` (${m.obstacles})` : ''}</span>
          </label>
          <span className="ps__hint">
            {pick === 'goal' && 'Click the image to place the goal (B).'}
            {pick === 'start' && 'Click the image to place the start (A).'}
            {pick === null && 'Change settings and press Plan, or move A / B.'}
          </span>
        </div>
      </div>

      <aside className="pw__side" aria-label="Path sketch settings and results">
        <section className="pw__section">
          <h2 className="pw__title">Path sketch around rock candidates</h2>
          <p className="pw__summary">
            Rock candidates become no-go zones and Theta* (the planner used on the orbital terrain) draws the cheapest
            path between A and B <strong>on this image</strong>. It shows the idea of hazard avoidance; it is not the route
            the rover would drive.
          </p>
          <div className="ps__picks">
            <button type="button" className={`ds-button${pick === 'start' ? ' is-active' : ''}`} onClick={() => setPick('start')}>
              Set start (A)
            </button>
            <button type="button" className={`ds-button${pick === 'goal' ? ' is-active' : ''}`} onClick={() => setPick('goal')}>
              Set goal (B)
            </button>
            <button
              type="button"
              className="ds-button"
              title="Quick start: put B in the middle of the image"
              onClick={() => {
                const centre = { x: 0.5, y: 0.55 }
                setGoal(centre)
                setPick(null)
                void plan(centre, start)
              }}
            >
              Goal at centre
            </button>
            {start && (
              <button
                type="button"
                className="ds-button"
                onClick={() => {
                  setStart(null)
                  if (goal) void plan(goal, null)
                }}
              >
                Reset A
              </button>
            )}
          </div>
          <p className="ps__note">A defaults to the bottom centre of the image (the ground nearest the camera).</p>

          <label className="ps__field">
            <span className="label">Obstacle detector</span>
            <select value={detector} onChange={(e) => setDetector(e.target.value as SketchDetector)}>
              <option value="blobs">Blob candidates (DoG)</option>
              <option value="contours">Contour candidates</option>
            </select>
          </label>
          <label className="ps__field">
            <span className="label">
              Clearance <span className="mono">×{formatNumber(clearance, 1)}</span>
            </span>
            <input type="range" min={1} max={4} step={0.1} value={clearance} onChange={(e) => setClearance(Number(e.target.value))} />
          </label>
          <label className="ps__field">
            <span className="label">
              Roughness weight <span className="mono">{formatNumber(roughness, 1)}</span>
            </span>
            <input type="range" min={0} max={10} step={0.5} value={roughness} onChange={(e) => setRoughness(Number(e.target.value))} />
          </label>
          <label className="pf__bool">
            <input type="checkbox" checked={autoHorizon} onChange={(e) => setAutoHorizon(e.target.checked)} />
            <span>Estimate horizon automatically</span>
          </label>
          {!autoHorizon && (
            <label className="ps__field">
              <span className="label">
                Horizon <span className="mono">{Math.round(horizon * 100)} %</span> from the top
              </span>
              <input type="range" min={0} max={0.75} step={0.01} value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} />
            </label>
          )}
          <button type="button" className="ds-button xi__go pw__run" disabled={!goal || running} onClick={() => void plan()}>
            {running ? 'Planning…' : goal ? 'Plan path' : 'Place the goal (B) first'}
          </button>
          {error && (
            <p className="xi__error" role="alert">
              {error}
            </p>
          )}
        </section>

        {result && m && (
          <section className="pw__section">
            <div className="ps__badges">
              <ProvenanceBadge provenance={result.provenance} />
              <span className="ps__method">ALGORITHMIC · IMAGE SPACE</span>
            </div>
            {!result.found && (
              <p className="xi__error" role="alert">
                No path: {result.reason}
              </p>
            )}
            <DataList
              items={[
                { label: 'Path length', value: result.found ? `${formatNumber(m.length_px)} px` : '—' },
                { label: 'Straight line', value: `${formatNumber(m.straight_px)} px` },
                { label: 'Detour', value: m.detour_pct === null ? '—' : `${formatNumber(m.detour_pct, 1)} %` },
                { label: 'Closest candidate', value: m.min_clearance_px === null ? '—' : `${formatNumber(m.min_clearance_px)} px` },
                { label: 'Candidates', value: `${m.obstacles} · ${m.blocking_straight_line} on straight line` },
                { label: 'Horizon', value: `${Math.round(result.horizon * 100)} % ${result.horizon_auto ? '(auto)' : '(manual)'}` },
                { label: 'Grid', value: `${m.grid[0]}×${m.grid[1]} · ${formatNumber(m.elapsed_ms)} ms` },
              ]}
            />
            <h3 className="label ps__sub">Why this path</h3>
            <ul className="ps__list">
              {result.explanation.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            <details className="ps__details">
              <summary className="label">Assumptions and limitations</summary>
              <ul className="ps__list">
                {result.assumptions.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <ul className="ps__list ps__list--warn">
                {result.limitations.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </details>
          </section>
        )}
      </aside>
    </div>
  )
}
