import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import type { ImageSummary } from '../../api/types'
import { formatSol } from '../../lib/format'
import { FIT, type View } from './zoom'
import { ZoomViewer } from './ZoomViewer'

interface CompareViewProps {
  a: ImageSummary
  b: ImageSummary
  /** True only for a verified left/right pair from the same acquisition. */
  stereo: boolean
  onClose: () => void
}

type Mode = 'side' | 'swipe'

function Caption({ image, tag }: { image: ImageSummary; tag: string }) {
  return (
    <span className="cmp__caption mono">
      <strong>{tag}</strong> {image.camera.instrument} · SOL {formatSol(image.sol)}
      {image.lmst ? ` · ${image.lmst}` : ''}
    </span>
  )
}

export function CompareView({ a, b, stereo, onClose }: CompareViewProps) {
  const [mode, setMode] = useState<Mode>('side')
  const [view, setView] = useState<View>(FIT)
  const [split, setSplit] = useState(50)
  const swipeRef = useRef<HTMLDivElement | null>(null)

  const moveHandle = (event: PointerEvent<HTMLDivElement>) => {
    if (!(event.buttons & 1) || !swipeRef.current) return
    const rect = swipeRef.current.getBoundingClientRect()
    setSplit(Math.min(100, Math.max(0, ((event.clientX - rect.left) / rect.width) * 100)))
  }
  const onHandleKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 10 : 2
    if (event.key === 'ArrowLeft') setSplit((s) => Math.max(0, s - step))
    else if (event.key === 'ArrowRight') setSplit((s) => Math.min(100, s + step))
    else return
    event.preventDefault()
    event.stopPropagation()
  }

  return (
    <div className="cmp">
      <div className="cmp__bar">
        <div className="cmp__modes" role="radiogroup" aria-label="Comparison mode">
          {(['side', 'swipe'] as const).map((m) => (
            <button key={m} type="button" role="radio" aria-checked={mode === m} className={mode === m ? 'is-active' : ''} onClick={() => setMode(m)}>
              {m === 'side' ? 'Side by side' : 'Swipe'}
            </button>
          ))}
        </div>
        <p className="cmp__note">
          {stereo
            ? 'Real stereo pair, captured together. The horizontal shift between eyes is parallax: nearer objects shift more. Phases 3–4 use it for depth.'
            : 'Different camera or time: differences mix viewpoint, lighting and time. This is a visual comparison, not change detection.'}
        </p>
        <button type="button" className="ds-button" onClick={onClose}>
          Close comparison
        </button>
      </div>

      {mode === 'side' ? (
        <div className="cmp__side">
          <ZoomViewer layers={[{ src: a.preview_url, alt: `A: ${a.image_id}` }]} view={view} onViewChange={setView} label="Image A">
            <Caption image={a} tag="A" />
          </ZoomViewer>
          <ZoomViewer layers={[{ src: b.preview_url, alt: `B: ${b.image_id}` }]} view={view} onViewChange={setView} label="Image B">
            <Caption image={b} tag="B" />
          </ZoomViewer>
        </div>
      ) : (
        <div className="cmp__swipe" ref={swipeRef}>
          <ZoomViewer
            layers={[
              { src: a.preview_url, alt: `A: ${a.image_id}` },
              { src: b.preview_url, alt: `B: ${b.image_id}`, clipLeftPercent: split },
            ]}
            view={view}
            onViewChange={setView}
            label="Swipe comparison"
          >
            <Caption image={a} tag="A" />
            <span className="cmp__caption cmp__caption--right mono">
              <strong>B</strong> {b.camera.instrument} · SOL {formatSol(b.sol)}
            </span>
            <div
              className="cmp__handle"
              data-no-pan
              style={{ left: `${split}%` }}
              role="slider"
              tabIndex={0}
              aria-label="Swipe position (A left, B right)"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(split)}
              onPointerDown={(event) => event.currentTarget.setPointerCapture?.(event.pointerId)}
              onPointerMove={moveHandle}
              onKeyDown={onHandleKey}
            >
              <span aria-hidden="true" />
            </div>
          </ZoomViewer>
        </div>
      )}
    </div>
  )
}
