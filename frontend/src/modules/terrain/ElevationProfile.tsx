import { useMemo, useState, type PointerEvent } from 'react'
import { formatNumber } from '../../lib/format'
import { profileAt } from './geometry'

export interface ProfileSeries {
  key: string
  label: string
  color: string
  dash?: string
  profile: [number, number][]
}

const W = 640
const H = 190
const PAD = { left: 52, right: 12, top: 10, bottom: 26 }

function niceTicks(min: number, max: number, count: number): number[] {
  const span = max - min || 1
  const raw = span / count
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ?? magnitude * 10
  const ticks = []
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(Math.round(v * 1000) / 1000)
  return ticks
}

/** Elevation vs. distance along each route: one shared y axis (metres), legend, hover crosshair. */
export function ElevationProfile({ series }: { series: ProfileSeries[] }) {
  const [hoverD, setHoverD] = useState<number | null>(null)
  const scale = useMemo(() => {
    const points = series.flatMap((s) => s.profile)
    if (points.length < 2) return null
    const maxD = Math.max(...points.map((p) => p[0]))
    const zs = points.map((p) => p[1])
    const minZ = Math.min(...zs)
    const maxZ = Math.max(...zs)
    const pad = Math.max(1, (maxZ - minZ) * 0.08)
    const z0 = minZ - pad
    const z1 = maxZ + pad
    const innerW = W - PAD.left - PAD.right
    const innerH = H - PAD.top - PAD.bottom
    return {
      maxD,
      z0,
      z1,
      x: (d: number) => PAD.left + (d / maxD) * innerW,
      y: (z: number) => PAD.top + innerH - ((z - z0) / (z1 - z0)) * innerH,
      invX: (px: number) => ((px - PAD.left) / innerW) * maxD,
    }
  }, [series])

  if (!scale) return <p className="tn-muted">Run a plan to see elevation profiles.</p>

  const onMove = (event: PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const d = scale.invX(((event.clientX - rect.left) / rect.width) * W)
    setHoverD(d >= 0 && d <= scale.maxD ? d : null)
  }
  const readings = hoverD === null ? [] : series.map((s) => ({ s, z: profileAt(s.profile, hoverD) })).filter((r) => r.z !== null)

  return (
    <div className="tn-profile">
      <ul className="tn-legend" aria-label="Profile legend">
        {series.map((s) => (
          <li key={s.key}>
            <svg width="22" height="8" aria-hidden="true">
              <line x1="0" x2="22" y1="4" y2="4" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash} />
            </svg>
            {s.label}
          </li>
        ))}
      </ul>
      <div className="tn-profile__plot">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label="Elevation along each route"
          onPointerMove={onMove}
          onPointerLeave={() => setHoverD(null)}
        >
          {niceTicks(scale.z0, scale.z1, 4).map((z) => (
            <g key={z} className="tn-grid">
              <line x1={PAD.left} x2={W - PAD.right} y1={scale.y(z)} y2={scale.y(z)} />
              <text x={PAD.left - 6} y={scale.y(z) + 3} textAnchor="end">
                {formatNumber(z, 0)} m
              </text>
            </g>
          ))}
          {niceTicks(0, scale.maxD, 5).map((d) => (
            <text key={d} className="tn-axis" x={scale.x(d)} y={H - 8} textAnchor="middle">
              {d >= 1000 ? `${(d / 1000).toFixed(1)} km` : `${d} m`}
            </text>
          ))}
          {series.map((s) => (
            <polyline
              key={s.key}
              className="tn-profile__line"
              stroke={s.color}
              strokeDasharray={s.dash}
              points={s.profile.map(([d, z]) => `${scale.x(d).toFixed(1)},${scale.y(z).toFixed(1)}`).join(' ')}
            />
          ))}
          {hoverD !== null && (
            <g>
              <line className="tn-crosshair" x1={scale.x(hoverD)} x2={scale.x(hoverD)} y1={PAD.top} y2={H - PAD.bottom} />
              {readings.map(({ s, z }) => (
                <circle key={s.key} className="tn-profile__dot" cx={scale.x(hoverD)} cy={scale.y(z!)} r={4} fill={s.color} />
              ))}
            </g>
          )}
        </svg>
        {hoverD !== null && readings.length > 0 && (
          <div
            className="tn-tooltip mono"
            style={{ left: `${(scale.x(hoverD) / W) * 100}%`, transform: `translateX(${scale.x(hoverD) / W > 0.6 ? '-105%' : '8px'})` }}
            role="status"
          >
            <strong>{hoverD >= 1000 ? `${(hoverD / 1000).toFixed(2)} km` : `${hoverD.toFixed(0)} m`}</strong>
            {readings.map(({ s, z }) => (
              <span key={s.key}>
                <i style={{ background: s.color }} aria-hidden="true" /> {s.label}: {formatNumber(z, 1)} m
              </span>
            ))}
          </div>
        )}
      </div>
      <p className="tn-muted">Elevation relative to the Mars areoid, sampled from the 1 m DEM along each route.</p>
    </div>
  )
}
