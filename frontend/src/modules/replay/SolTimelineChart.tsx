import { useState } from 'react'
import type { SolTimeline, TimelineImage } from '../../api/types'
import { formatNumber } from '../../lib/format'
import { formatLmstHours, lmstWindow } from './playback'

interface Props {
  timeline: SolTimeline
  activeSequence: string | null
  onImage: (image: TimelineImage) => void
}

interface Hover {
  left: number
  row: number
  lines: string[]
  thumb?: string
}

export function SolTimelineChart({ timeline, activeSequence, onImage }: Props) {
  const [hover, setHover] = useState<Hover | null>(null)
  const cameras = [...new Map(timeline.images.map((i) => [i.camera.instrument, i.camera])).values()]
  const driveHours = timeline.drives.flatMap((d) =>
    d.start_lmst_h !== null && d.end_lmst_h !== null ? [d.start_lmst_h, d.end_lmst_h] : [],
  )
  const hours = [...timeline.images.flatMap((i) => (i.lmst_h === null ? [] : [i.lmst_h])), ...driveHours]
  const [low, high] = lmstWindow(hours)
  const pos = (h: number) => ((h - low) / (high - low)) * 100
  const ticks: number[] = []
  const every = high - low > 12 ? 3 : high - low > 6 ? 2 : 1
  for (let h = Math.ceil(low / every) * every; h <= high; h += every) ticks.push(h)
  const showDrives = timeline.drives.length > 0
  const unplaced = timeline.images.filter((i) => i.lmst_h === null).length
  const activeKey = activeSequence?.split('-').slice(1).join('-') ?? null

  return (
    <div className="rp-tl">
      <div className="rp-tl__grid" onMouseLeave={() => setHover(null)}>
        {cameras.map((camera, row) => (
          <div className="rp-tl__row" key={camera.instrument}>
            <span className="rp-tl__label" title={camera.label}>
              {camera.instrument.replaceAll('_', ' ')}
            </span>
            <div className="rp-tl__track">
              {ticks.map((t) => (
                <span key={t} className="rp-tl__gridline" style={{ left: `${pos(t)}%` }} aria-hidden="true" />
              ))}
              {timeline.images
                .filter((i) => i.camera.instrument === camera.instrument && i.lmst_h !== null)
                .map((image) => {
                  const left = pos(image.lmst_h ?? 0)
                  const inActive = activeKey === `${image.camera.instrument}-${image.sequence_id ?? 'NOSEQ'}`
                  return (
                    <button
                      key={image.image_id}
                      type="button"
                      className={`rp-tl__dot ${inActive ? 'is-active' : ''}`}
                      style={{ left: `${left}%` }}
                      aria-label={`${camera.instrument} image at LMST ${image.lmst ?? 'unknown'}, ${image.image_id}`}
                      onMouseEnter={() =>
                        setHover({
                          left,
                          row,
                          thumb: image.thumb_url,
                          lines: [
                            `LMST ${image.lmst ?? '—'}`,
                            camera.label,
                            image.sequence_id ? `sequence ${image.sequence_id}` : 'no sequence id',
                          ],
                        })
                      }
                      onFocus={() => setHover({ left, row, thumb: image.thumb_url, lines: [`LMST ${image.lmst ?? '—'}`, camera.label] })}
                      onClick={() => onImage(image)}
                    />
                  )
                })}
            </div>
          </div>
        ))}
        {showDrives && (
          <div className="rp-tl__row">
            <span className="rp-tl__label">REAL DRIVES</span>
            <div className="rp-tl__track">
              {ticks.map((t) => (
                <span key={t} className="rp-tl__gridline" style={{ left: `${pos(t)}%` }} aria-hidden="true" />
              ))}
              {timeline.drives
                .filter((d) => d.start_lmst_h !== null && d.end_lmst_h !== null)
                .map((d) => {
                  const left = pos(d.start_lmst_h ?? 0)
                  const width = Math.max(0.6, pos(d.end_lmst_h ?? 0) - left)
                  return (
                    <span
                      key={d.index}
                      className="rp-tl__drive"
                      style={{ left: `${left}%`, width: `${width}%` }}
                      onMouseEnter={() =>
                        setHover({
                          left: left + width / 2,
                          row: cameras.length,
                          lines: [
                            `Drive ${formatNumber(d.length_m, 1)} m`,
                            `LMST ${formatLmstHours(d.start_lmst_h)}–${formatLmstHours(d.end_lmst_h)} (derived)`,
                            `${d.from_rmc ?? '—'} → ${d.to_rmc ?? '—'}`,
                          ],
                        })
                      }
                    />
                  )
                })}
            </div>
          </div>
        )}
        {hover && (
          <div
            className={`rp-tooltip rp-tooltip--tl ${hover.left > 65 ? 'rp-tooltip--left' : ''}`}
            style={{ left: `calc(112px + (100% - 112px) * ${hover.left / 100})`, top: `${(hover.row + 1) * 28 + 4}px` }}
            role="status"
          >
            {hover.thumb && <img src={hover.thumb} alt="" width={96} height={72} />}
            {hover.lines.map((line) => (
              <span key={line}>{line}</span>
            ))}
          </div>
        )}
      </div>
      <div className="rp-tl__axis mono" aria-hidden="true">
        {ticks.map((t) => (
          <span key={t} style={{ left: `calc(112px + (100% - 112px) * ${pos(t) / 100})` }}>
            {formatLmstHours(t)}
          </span>
        ))}
      </div>
      <p className="rp-note">
        Local Mean Solar Time on Mars.
        {timeline.lmst_calibration && showDrives && (
          <>
            {' '}
            Drive times placed from the spacecraft clock, calibrated on {timeline.lmst_calibration.samples} images (max
            residual {formatNumber(timeline.lmst_calibration.max_residual_s, 1)} s).
          </>
        )}
        {unplaced > 0 && ` ${unplaced} image(s) without LMST are not shown.`}
      </p>
    </div>
  )
}
