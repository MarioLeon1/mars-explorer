import { useMemo, useState, type PointerEvent } from 'react'
import { api } from '../../api/client'
import type { WaypointPoint } from '../../api/types'
import { useApi } from '../../api/useApi'
import { Panel } from '../../design-system/Panel'
import { ErrorState, SkeletonBlock } from '../../design-system/primitives'
import { formatKilometres, formatMetres, formatNumber } from '../../lib/format'
import { formatLength } from '../../lib/geo'
import { buildTraversePlot, nearestByDistance, profilePoints, type ProfilePoint } from './traverse'

const MAP_W = 320
const MAP_H = 190
const PROFILE_W = 320
const PROFILE_H = 96
const PROFILE_PAD = { left: 40, right: 8, top: 8, bottom: 16 }

function toSvgPoint(event: PointerEvent<SVGSVGElement>) {
  const svg = event.currentTarget
  const matrix = svg.getScreenCTM()
  if (!matrix) return null
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse())
  return { x: point.x, y: point.y }
}

function Tooltip({ waypoint, x, y, width }: { waypoint: WaypointPoint; x: number; y: number; width: number }) {
  const left = (x / width) * 100
  return (
    <div
      className="trav__tooltip mono"
      style={{ left: `${left}%`, top: `${y}%`, transform:`translate(${left > 60 ? '-100%' : '0'}, -100%)` }}
      role="status"
    >
      <strong>SOL {waypoint.sol}</strong>
      <span>{formatKilometres(waypoint.odometry_total_m)}</span>
      <span>{formatMetres(waypoint.elevation_m, 0)}</span>
    </div>
  )
}

export function TraversePanel() {
  const waypoints = useApi('waypoints', api.waypoints)
  const mission = useApi('mission', api.mission)
  const [hovered, setHovered] = useState<number | null>(null)

  const items = useMemo(() => waypoints.state.data?.items ?? [], [waypoints.state.data])
  const landing = mission.state.data?.landing_site ?? null

  const plot = useMemo(
    () => (landing && items.length ? buildTraversePlot(items, landing, MAP_W, MAP_H, 14) : null),
    [items, landing],
  )
  const profile = useMemo(() => profilePoints(items), [items])

  const profileScale = useMemo(() => {
    if (profile.length < 2) return null
    const maxKm = Math.max(...profile.map((p) => p.km))
    const elevations = profile.map((p) => p.elevation)
    const minE = Math.floor(Math.min(...elevations) / 100) * 100
    const maxE = Math.ceil(Math.max(...elevations) / 100) * 100
    const innerW = PROFILE_W - PROFILE_PAD.left - PROFILE_PAD.right
    const innerH = PROFILE_H - PROFILE_PAD.top - PROFILE_PAD.bottom
    const sx = (km: number) => PROFILE_PAD.left + (km / maxKm) * innerW
    const sy = (e: number) => PROFILE_PAD.top + innerH - ((e - minE) / (maxE - minE || 1)) * innerH
    return { maxKm, minE, maxE, sx, sy }
  }, [profile])

  const hoveredWaypoint = hovered !== null ? items[hovered] : undefined
  const hoveredPlot = hovered !== null ? plot?.points[hovered] : undefined
  const hoveredProfile: ProfilePoint | undefined =
    hovered !== null ? profile.find((p) => p.index === hovered) : undefined
  const current = plot?.points[plot.points.length - 1]
  const first = profile[0]
  const last = profile[profile.length - 1]
  const climb = first && last ? last.elevation - first.elevation : null

  const onMapMove = (event: PointerEvent<SVGSVGElement>) => {
    const p = toSvgPoint(event)
    if (!p || !plot) return
    setHovered(nearestByDistance(plot.points, p.x, p.y)?.index ?? null)
  }

  const onProfileMove = (event: PointerEvent<SVGSVGElement>) => {
    const p = toSvgPoint(event)
    if (!p || !profileScale) return
    let best: ProfilePoint | null = null
    for (const point of profile) {
      if (!best || Math.abs(profileScale.sx(point.km) - p.x) < Math.abs(profileScale.sx(best.km) - p.x)) best = point
    }
    setHovered(best?.index ?? null)
  }

  const error = waypoints.state.status === 'error' ? waypoints.state.error : null

  return (
    <Panel
      title="Traverse"
      className="trav"
      meta={items.length ? <span className="mono">{formatNumber(items.length)} fixes</span> : undefined}
      footer="Real localizations (JPL MMGIS), local equirectangular projection. Schematic — not a terrain map."
    >
      {error ? (
        <ErrorState title="Traverse unavailable" message={error.message} onRetry={waypoints.retry} />
      ) : !plot ? (
        <SkeletonBlock lines={6} />
      ) : (
        <>
          <div className="trav__plot">
            <svg
              viewBox={`0 0 ${MAP_W} ${MAP_H}`}
              role="img"
              aria-label={`Perseverance traverse: ${items.length} real localizations from sol ${items[0]?.sol} to sol ${items[items.length - 1]?.sol}`}
              onPointerMove={onMapMove}
              onPointerLeave={() => setHovered(null)}
            >
              <polyline
                className="trav__path"
                points={plot.points.map((p) => `${p.sx.toFixed(1)},${p.sy.toFixed(1)}`).join(' ')}
              />
              <g className="trav__landing" transform={`translate(${plot.origin.sx} ${plot.origin.sy})`}>
                <path d="M0 -5 L5 0 L0 5 L-5 0 Z" />
                {/* keep the label inside the plot: put it on the side with more room */}
                <text
                  x={plot.origin.sx > MAP_W * 0.7 ? -8 : 8}
                  y={16}
                  textAnchor={plot.origin.sx > MAP_W * 0.7 ? 'end' : 'start'}
                >
                  Landing
                </text>
              </g>
              {current && (
                <g className="trav__current" transform={`translate(${current.sx} ${current.sy})`}>
                  <circle r="7" className="trav__current-ring" />
                  <circle r="4" />
                </g>
              )}
              {hoveredPlot && <circle className="trav__hover" cx={hoveredPlot.sx} cy={hoveredPlot.sy} r="4" />}
              <g className="trav__north" transform={`translate(${MAP_W - 16} 18)`}>
                <path d="M0 -9 L4 3 L0 1 L-4 3 Z" />
                <text y="14">N</text>
              </g>
              <g className="trav__scale" transform={`translate(14 ${MAP_H - 12})`}>
                <path d={`M0 -4 V0 H${plot.scaleBar.length} V-4`} />
                <text x={plot.scaleBar.length + 6} y="2">
                  {formatLength(plot.scaleBar.metres)}
                </text>
              </g>
            </svg>
            {hoveredWaypoint && hoveredPlot && (
              <Tooltip waypoint={hoveredWaypoint} x={hoveredPlot.sx} y={(hoveredPlot.sy / MAP_H) * 100} width={MAP_W} />
            )}
          </div>

          {profileScale && (
            <div className="trav__profile">
              <div className="trav__profile-head">
                <span className="label">Elevation along traverse</span>
                {climb !== null && <span className="mono trav__climb">{`${climb >= 0 ? '+' : ''}${formatNumber(climb, 0)} m net`}</span>}
              </div>
              <svg
                viewBox={`0 0 ${PROFILE_W} ${PROFILE_H}`}
                role="img"
                aria-label={`Elevation from ${formatMetres(first?.elevation, 0)} to ${formatMetres(last?.elevation, 0)} over ${formatKilometres(profileScale.maxKm * 1000)}`}
                onPointerMove={onProfileMove}
                onPointerLeave={() => setHovered(null)}
              >
                {[profileScale.minE, (profileScale.minE + profileScale.maxE) / 2, profileScale.maxE].map((e) => (
                  <g key={e} className="trav__grid">
                    <line x1={PROFILE_PAD.left} x2={PROFILE_W - PROFILE_PAD.right} y1={profileScale.sy(e)} y2={profileScale.sy(e)} />
                    <text x={PROFILE_PAD.left - 6} y={profileScale.sy(e) + 3}>
                      {formatNumber(e, 0)}
                    </text>
                  </g>
                ))}
                <g className="trav__grid">
                  <text className="trav__tick--start" x={PROFILE_PAD.left} y={PROFILE_H - 3}>
                    0 km
                  </text>
                  <text className="trav__tick--end" x={PROFILE_W - PROFILE_PAD.right} y={PROFILE_H - 3}>
                    {formatNumber(profileScale.maxKm, 1)} km
                  </text>
                </g>
                <polyline
                  className="trav__elev"
                  points={profile
                    .map((p) => `${profileScale.sx(p.km).toFixed(1)},${profileScale.sy(p.elevation).toFixed(1)}`)
                    .join(' ')}
                />
                {hoveredProfile && (
                  <>
                    <line
                      className="trav__crosshair"
                      x1={profileScale.sx(hoveredProfile.km)}
                      x2={profileScale.sx(hoveredProfile.km)}
                      y1={PROFILE_PAD.top}
                      y2={PROFILE_H - PROFILE_PAD.bottom}
                    />
                    <circle
                      className="trav__hover"
                      cx={profileScale.sx(hoveredProfile.km)}
                      cy={profileScale.sy(hoveredProfile.elevation)}
                      r="4"
                    />
                  </>
                )}
              </svg>
              <p className="trav__axis-note">metres relative to the Mars areoid · distance = rover odometry</p>
            </div>
          )}
        </>
      )}
    </Panel>
  )
}
