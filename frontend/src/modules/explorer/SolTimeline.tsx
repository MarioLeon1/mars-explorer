import { useState, type PointerEvent } from 'react'
import type { SolSummary } from '../../api/types'
import { formatNumber } from '../../lib/format'

interface SolTimelineProps {
  sols: SolSummary[]
  /** Latest sol published by NASA (axis end); falls back to the newest stored sol. */
  latestSol: number | null
  selectedSol: number | undefined
  onSelect: (sol: number | undefined) => void
}

const W = 1000
const H = 52
const PAD_X = 12
const BASE = 36

/** Mission timeline: where the locally stored sols sit within the whole mission. */
export function SolTimeline({ sols, latestSol, selectedSol, onSelect }: SolTimelineProps) {
  const [hover, setHover] = useState<SolSummary | null>(null)
  const end = Math.max(latestSol ?? 0, ...sols.map((s) => s.sol), 1)
  const max = Math.max(1, ...sols.map((s) => s.image_count))
  const x = (sol: number) => PAD_X + (sol / end) * (W - 2 * PAD_X)
  const ticks = Array.from({ length: Math.floor(end / 250) + 1 }, (_, i) => i * 250).filter((t) => t <= end)

  const onMove = (event: PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    const sx = ((event.clientX - rect.left) / rect.width) * W
    let best: SolSummary | null = null
    for (const s of sols) if (!best || Math.abs(x(s.sol) - sx) < Math.abs(x(best.sol) - sx)) best = s
    setHover(best && Math.abs(x(best.sol) - sx) < 24 ? best : null)
  }

  return (
    <div className="xt">
      <div className="xt__head">
        <span className="label">Mission timeline</span>
        <span className="xt__meta mono">
          {hover
            ? `SOL ${hover.sol} · ${hover.image_count} images · ${hover.instruments.length} cameras — click to filter`
            : `${sols.length} of ${formatNumber(end + 1)} sols stored locally`}
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="group"
        aria-label="Stored sols along the mission"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
        onClick={() => hover && onSelect(selectedSol === hover.sol ? undefined : hover.sol)}
      >
        <line className="xt__axis" x1={PAD_X} x2={W - PAD_X} y1={BASE} y2={BASE} />
        {ticks.map((t) => (
          <g key={t}>
            <line className="xt__tick" x1={x(t)} x2={x(t)} y1={BASE} y2={BASE + 4} />
            <text className="xt__label" x={x(t)} y={H - 2}>
              {t}
            </text>
          </g>
        ))}
        {sols.map((s) => {
          const h = 6 + (s.image_count / max) * (BASE - 10)
          const selected = s.sol === selectedSol
          return (
            <rect
              key={s.sol}
              className={`xt__bar${selected ? ' is-selected' : ''}${hover?.sol === s.sol ? ' is-hover' : ''}`}
              x={x(s.sol) - 2}
              y={BASE - h}
              width={4}
              height={h}
              rx={1}
            >
              <title>{`Sol ${s.sol}: ${s.image_count} images`}</title>
            </rect>
          )
        })}
      </svg>
      <div className="visually-hidden">
        {sols.map((s) => (
          <button key={s.sol} type="button" onClick={() => onSelect(selectedSol === s.sol ? undefined : s.sol)}>
            Filter to sol {s.sol} ({s.image_count} images)
          </button>
        ))}
      </div>
    </div>
  )
}
