/**
 * Zoom/pan maths for the image viewer.
 *
 * The view is stored in NORMALISED terms — zoom relative to "fit" and the view centre as a
 * fraction of the image — so it can be shared between images of different pixel sizes
 * (e.g. the 1200 px JPEG and the full-resolution PNG, or the two images being compared).
 */

export interface View {
  /** 1 = whole image fits the container */
  zoom: number
  /** view centre as a fraction of image width / height (0..1) */
  cx: number
  cy: number
}

export interface Size {
  width: number
  height: number
}

export interface Transform {
  /** screen px per image px */
  scale: number
  /** top-left of the image in container px */
  x: number
  y: number
}

export const FIT: View = { zoom: 1, cx: 0.5, cy: 0.5 }
/** Never magnify beyond 8 screen px per image px. */
export const MAX_PIXEL_SCALE = 8

export function fitScale(natural: Size, container: Size): number {
  if (natural.width <= 0 || natural.height <= 0) return 1
  return Math.min(container.width / natural.width, container.height / natural.height)
}

export function maxZoom(natural: Size, container: Size): number {
  return Math.max(1, MAX_PIXEL_SCALE / fitScale(natural, container))
}

export function toTransform(view: View, natural: Size, container: Size): Transform {
  const scale = fitScale(natural, container) * view.zoom
  return {
    scale,
    x: container.width / 2 - view.cx * natural.width * scale,
    y: container.height / 2 - view.cy * natural.height * scale,
  }
}

function clampAxis(center: number, visibleFraction: number): number {
  const half = visibleFraction / 2
  if (half >= 0.5) return 0.5 // the whole axis is visible: keep it centred
  return Math.min(1 - half, Math.max(half, center))
}

/** Keep the image covering the viewport (no panning into empty space). */
export function clampView(view: View, natural: Size, container: Size): View {
  const zoom = Math.min(maxZoom(natural, container), Math.max(1, view.zoom))
  const scale = fitScale(natural, container) * zoom
  return {
    zoom,
    cx: clampAxis(view.cx, container.width / (natural.width * scale)),
    cy: clampAxis(view.cy, container.height / (natural.height * scale)),
  }
}

/** Zoom by `factor` keeping the image point under (px, py) fixed on screen. */
export function zoomAt(view: View, factor: number, px: number, py: number, natural: Size, container: Size): View {
  const t = toTransform(view, natural, container)
  const ix = (px - t.x) / t.scale
  const iy = (py - t.y) / t.scale
  const zoom = Math.min(maxZoom(natural, container), Math.max(1, view.zoom * factor))
  const scale = fitScale(natural, container) * zoom
  const x = px - ix * scale
  const y = py - iy * scale
  return clampView(
    {
      zoom,
      cx: (container.width / 2 - x) / (natural.width * scale),
      cy: (container.height / 2 - y) / (natural.height * scale),
    },
    natural,
    container,
  )
}

/** Pan by a screen-space delta (drag right => image moves right). */
export function panBy(view: View, dx: number, dy: number, natural: Size, container: Size): View {
  const scale = fitScale(natural, container) * view.zoom
  return clampView(
    { ...view, cx: view.cx - dx / (natural.width * scale), cy: view.cy - dy / (natural.height * scale) },
    natural,
    container,
  )
}

/** View showing the image at native resolution (1 image px = 1 screen px), centred. */
export function nativeView(view: View, natural: Size, container: Size): View {
  return clampView({ ...view, zoom: 1 / fitScale(natural, container) }, natural, container)
}
