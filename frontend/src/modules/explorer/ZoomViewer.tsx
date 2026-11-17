import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
  type RefObject,
} from 'react'
import { clampView, FIT, nativeView, panBy, toTransform, zoomAt, type Size, type View } from './zoom'

export interface ViewerLayer {
  src: string
  alt: string
  /** Hide the left part of this layer (0–100 %) — used by swipe comparison. */
  clipLeftPercent?: number
  /** 0–1, default 1 */
  opacity?: number
}

interface ZoomViewerProps {
  layers: ViewerLayer[]
  view: View
  onViewChange: (view: View) => void
  /** Extra overlay content (labels, swipe handle). Pointer events on it do not pan. */
  children?: ReactNode
  label?: string
  onNaturalSize?: (size: Size) => void
  /**
   * Vector overlay drawn in IMAGE pixel coordinates of the first layer (it zooms and pans with
   * the image). `scale` = screen px per image px, to keep markers a constant on-screen size.
   */
  overlay?: (natural: Size, scale: number) => ReactNode
  /** Click (not drag) on the image, in fractions of the first layer's width/height. */
  onImageClick?: (x: number, y: number) => void
  /** Cursor style hint while clicking does something (e.g. annotating). */
  clickMode?: boolean
}

/** Pointer travel (px) below which a press counts as a click rather than a pan. */
const CLICK_SLOP = 4

const WHEEL_STEP = 1.0015
const BUTTON_STEP = 1.6
const KEY_PAN = 60

function useElementSize(ref: RefObject<HTMLElement | null>): Size {
  const [size, setSize] = useState<Size>({ width: 0, height: 0 })
  useEffect(() => {
    const element = ref.current
    if (!element) return
    const update = () => setSize({ width: element.clientWidth, height: element.clientHeight })
    update()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [ref])
  return size
}

export function ZoomViewer({
  layers,
  view,
  onViewChange,
  children,
  label,
  onNaturalSize,
  overlay,
  onImageClick,
  clickMode,
}: ZoomViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const container = useElementSize(containerRef)
  const [naturals, setNaturals] = useState<Record<string, Size>>({})
  const drag = useRef<{ x: number; y: number; id: number; travel: number } | null>(null)

  const reference = layers[0] ? naturals[layers[0].src] : undefined
  const ready = reference !== undefined && container.width > 0 && container.height > 0

  // Latest values for the native wheel listener (registered once, non-passive).
  const latest = useRef({ view, reference, container, onViewChange })
  useEffect(() => {
    latest.current = { view, reference, container, onViewChange }
  })

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    const onWheel = (event: WheelEvent) => {
      const { view: v, reference: natural, container: box, onViewChange: emit } = latest.current
      if (!natural) return
      event.preventDefault()
      const rect = element.getBoundingClientRect()
      const factor = WHEEL_STEP ** -event.deltaY
      emit(zoomAt(v, factor, event.clientX - rect.left, event.clientY - rect.top, natural, box))
    }
    element.addEventListener('wheel', onWheel, { passive: false })
    return () => element.removeEventListener('wheel', onWheel)
  }, [])

  const zoomCenter = useCallback(
    (factor: number) => {
      if (!reference) return
      onViewChange(zoomAt(view, factor, container.width / 2, container.height / 2, reference, container))
    },
    [container, onViewChange, reference, view],
  )

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0 || (event.target as HTMLElement).closest('[data-no-pan]')) return
    drag.current = { x: event.clientX, y: event.clientY, id: event.pointerId, travel: 0 }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const start = drag.current
    if (!start || start.id !== event.pointerId || !reference) return
    const dx = event.clientX - start.x
    const dy = event.clientY - start.y
    const travel = start.travel + Math.hypot(dx, dy)
    if (travel > CLICK_SLOP) onViewChange(panBy(view, dx, dy, reference, container))
    drag.current = { ...start, x: event.clientX, y: event.clientY, travel }
  }
  const endDrag = (event: PointerEvent<HTMLDivElement>) => {
    const start = drag.current
    drag.current = null
    if (!start || start.travel > CLICK_SLOP || !onImageClick || !reference || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const t = toTransform(view, reference, container)
    const x = (event.clientX - rect.left - t.x) / t.scale / reference.width
    const y = (event.clientY - rect.top - t.y) / t.scale / reference.height
    if (x >= 0 && x <= 1 && y >= 0 && y <= 1) onImageClick(x, y)
  }
  const cancelDrag = () => {
    drag.current = null
  }

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!reference) return
    const pan = (dx: number, dy: number) => onViewChange(panBy(view, dx, dy, reference, container))
    const handlers: Record<string, () => void> = {
      '+': () => zoomCenter(BUTTON_STEP),
      '=': () => zoomCenter(BUTTON_STEP),
      '-': () => zoomCenter(1 / BUTTON_STEP),
      '0': () => onViewChange(FIT),
      '1': () => onViewChange(nativeView(view, reference, container)),
    }
    if (view.zoom > 1) {
      Object.assign(handlers, {
        ArrowLeft: () => pan(KEY_PAN, 0),
        ArrowRight: () => pan(-KEY_PAN, 0),
        ArrowUp: () => pan(0, KEY_PAN),
        ArrowDown: () => pan(0, -KEY_PAN),
      })
    }
    const handler = handlers[event.key]
    if (handler) {
      handler()
      event.preventDefault()
      event.stopPropagation()
    }
  }

  const scalePercent = ready ? Math.round(toTransform(view, reference, container).scale * 100) : null

  return (
    <div className="zv">
      <div
        ref={containerRef}
        className={`zv__stage${view.zoom > 1 ? ' is-zoomed' : ''}${clickMode ? ' is-click-mode' : ''}`}
        tabIndex={0}
        role="group"
        aria-roledescription="zoomable image"
        aria-label={`${label ?? 'Image'} — scroll or +/- to zoom, drag or arrows to pan, 0 to fit, 1 for native pixels`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={cancelDrag}
        onDoubleClick={() => onViewChange(FIT)}
        onKeyDown={onKeyDown}
      >
        {layers.map((layer, index) => {
          const natural = naturals[layer.src]
          const transform = natural && container.width ? toTransform(clampView(view, natural, container), natural, container) : null
          return (
            <img
              key={`${index}:${layer.src}`}
              src={layer.src}
              alt={layer.alt}
              draggable={false}
              className="zv__img"
              style={{
                width: natural?.width,
                height: natural?.height,
                visibility: transform ? 'visible' : 'hidden',
                transform: transform ? `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})` : undefined,
                clipPath: layer.clipLeftPercent ? `inset(0 0 0 ${layer.clipLeftPercent}%)` : undefined,
                opacity: layer.opacity,
              }}
              onLoad={(event) => {
                const size = { width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight }
                setNaturals((current) => ({ ...current, [layer.src]: size }))
                if (index === 0) onNaturalSize?.(size)
              }}
            />
          )
        })}
        {ready && overlay && (() => {
          const t = toTransform(view, reference, container)
          return (
            <svg
              className="zv__overlay"
              width={reference.width}
              height={reference.height}
              viewBox={`0 0 ${reference.width} ${reference.height}`}
              style={{ transform: `translate(${t.x}px, ${t.y}px) scale(${t.scale})` }}
              aria-hidden="true"
            >
              {overlay(reference, t.scale)}
            </svg>
          )
        })()}
        {!ready && <div className="zv__loading" aria-hidden="true" />}
        {children}
      </div>
      <div className="zv__controls" data-no-pan>
        <button type="button" onClick={() => zoomCenter(1 / BUTTON_STEP)} aria-label="Zoom out" disabled={view.zoom <= 1}>
          −
        </button>
        <span className="zv__scale mono" aria-live="polite" title="Screen pixels per image pixel">
          {scalePercent !== null ? `${scalePercent}%` : '—'}
        </span>
        <button type="button" onClick={() => zoomCenter(BUTTON_STEP)} aria-label="Zoom in">
          +
        </button>
        <button type="button" onClick={() => onViewChange(FIT)} disabled={view.zoom === 1}>
          Fit
        </button>
        <button type="button" onClick={() => reference && onViewChange(nativeView(view, reference, container))}>
          1:1
        </button>
      </div>
    </div>
  )
}
