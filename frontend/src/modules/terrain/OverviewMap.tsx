import type { MouseEvent } from 'react'
import type { DrivePath, EN, Extent } from '../../api/types'
import { fromFraction, polyline, toFraction } from './geometry'

interface OverviewMapProps {
  extent: Extent
  drives: DrivePath[]
  roi: Extent | null
  onPick: (center: EN) => void
}

const W = 1480
const H = 548

/** Whole PLACES DEM (shaded relief) with the real traverse; click to centre the working map. */
export function OverviewMap({ extent, drives, roi, onPick }: OverviewMapProps) {
  const last = drives[drives.length - 1]
  const lastPoint = last?.points[last.points.length - 1]
  const onClick = (event: MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    onPick(fromFraction(extent, (event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height))
  }
  const box = roi
    ? (() => {
        const a = toFraction(extent, roi.e_min, roi.n_max)
        const b = toFraction(extent, roi.e_max, roi.n_min)
        return { x: a.x * W, y: a.y * H, w: (b.x - a.x) * W, h: (b.y - a.y) * H }
      })()
    : null
  return (
    <svg
      className="tn-overview"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Whole orbital DEM with the real Perseverance traverse; click to move the working map"
      onClick={onClick}
    >
      <image href="/api/terrain/overview.png" x={0} y={0} width={W} height={H} preserveAspectRatio="none" />
      {drives.map((d) => (
        <polyline key={d.index} className="tn-overview__drive" points={polyline(extent, d.points, W, H)} />
      ))}
      {lastPoint && (() => {
        const p = toFraction(extent, lastPoint[0], lastPoint[1])
        return <circle className="tn-overview__rover" cx={p.x * W} cy={p.y * H} r={9} />
      })()}
      {box && <rect className="tn-overview__roi" x={box.x} y={box.y} width={box.w} height={box.h} />}
    </svg>
  )
}
