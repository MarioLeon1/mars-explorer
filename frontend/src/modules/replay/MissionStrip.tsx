import { useMemo, useState, type MouseEvent } from 'react'
import type { SolActivity } from '../../api/types'
import { formatNumber } from '../../lib/format'

const W = 1000
const H = 100

interface MissionStripProps {
  sols: SolActivity[]
  selected: number | null
  onSelect: (sol: number) => void
}

/** Single series: real drive distance per sol (bars), plus ticks for sols with stored images. */
export function MissionStrip({ sols, selected, onSelect }: MissionStripProps) {
  const [hover, setHover] = useState<SolActivity | null>(null)
  const maxSol = Math.max(1, ...sols.map((s) => s.sol))
  const maxDrive = Math.max(1, ...sols.map((s) => s.drive_m))
  const step = W / (maxSol + 1)
  const bySol = useMemo(() => new Map(sols.map((s) => [s.sol, s])), [sols])
  const x = (sol: number) => (sol / (maxSol + 1)) * 100

  const nearest = (event: MouseEvent<HTMLDivElement>): SolActivity | null => {
    const box = event.currentTarget.getBoundingClientRect()
    const sol = Math.round(((event.clientX - box.left) / box.width) * (maxSol + 1))
    let best: SolActivity | null = null
    for (let d = 0; d <= Math.ceil((maxSol + 1) / 150); d++) {
      best = bySol.get(sol - d) ?? bySol.get(sol + d) ?? null
      if (best) break
    }
    return best
  }

  return (
    <div className="rp-strip">
      <div className="rp-strip__axis-y mono" aria-hidden="true">
        <span>{formatNumber(maxDrive)} m</span>
        <span>0</span>
      </div>
      <div
        className="rp-strip__plot"
        onMouseMove={(e) => setHover(nearest(e))}
        onMouseLeave={() => setHover(null)}
        onClick={(e) => {
          const target = nearest(e)
          if (target) onSelect(target.sol)
        }}
        role="img"
        aria-label={`Real drive distance per sol, ${sols.length} sols with activity. Click a sol to open it.`}
      >
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="rp-strip__svg" aria-hidden="true">
          <line x1="0" x2={W} y1={H - 0.5} y2={H - 0.5} className="rp-strip__base" />
          <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="rp-strip__grid" />
          {sols
            .filter((s) => s.drive_m > 0)
            .map((s) => {
              const h = Math.max(1.5, (s.drive_m / maxDrive) * (H - 4))
              return (
                <rect
                  key={s.sol}
                  x={s.sol * step}
                  y={H - h}
                  width={Math.max(step * 0.8, 0.8)}
                  height={h}
                  className="rp-strip__bar"
                />
              )
            })}
        </svg>
        <div className="rp-strip__ticks" aria-hidden="true">
          {sols
            .filter((s) => s.images > 0)
            .map((s) => (
              <span key={s.sol} className="rp-strip__tick" style={{ left: `${x(s.sol)}%` }} />
            ))}
        </div>
        {selected !== null && (
          <span className="rp-strip__cursor rp-strip__cursor--selected" style={{ left: `${x(selected)}%` }} />
        )}
        {hover && (
          <>
            <span className="rp-strip__cursor" style={{ left: `${x(hover.sol)}%` }} />
            <div
              className={`rp-tooltip ${x(hover.sol) > 70 ? 'rp-tooltip--left' : ''}`}
              style={{ left: `${x(hover.sol)}%` }}
              role="status"
            >
              <strong className="mono">Sol {hover.sol}</strong>
              <span>
                Drives <span className="mono">{hover.drives}</span> · <span className="mono">{formatNumber(hover.drive_m, 1)} m</span>
              </span>
              <span>
                Stored images <span className="mono">{hover.images}</span>
                {hover.sequences > 0 && (
                  <>
                    {' '}
                    · sequences <span className="mono">{hover.sequences}</span>
                  </>
                )}
              </span>
            </div>
          </>
        )}
      </div>
      <div className="rp-strip__axis-x mono" aria-hidden="true">
        <span>Sol 0</span>
        <span>Sol {Math.round(maxSol / 2)}</span>
        <span>Sol {maxSol}</span>
      </div>
      <p className="rp-strip__key">
        <span className="rp-key rp-key--bar" aria-hidden="true" /> drive distance (JPL traverse)
        <span className="rp-key rp-key--tick" aria-hidden="true" /> sol with images stored in this app
      </p>
    </div>
  )
}
