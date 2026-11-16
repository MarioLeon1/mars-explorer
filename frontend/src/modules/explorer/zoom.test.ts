import { describe, expect, it } from 'vitest'
import { clampView, FIT, fitScale, maxZoom, nativeView, panBy, toTransform, zoomAt } from './zoom'

const IMG = { width: 1280, height: 960 }
const BOX = { width: 800, height: 400 }

describe('zoom maths', () => {
  it('fits and centres the image', () => {
    expect(fitScale(IMG, BOX)).toBeCloseTo(400 / 960)
    const t = toTransform(FIT, IMG, BOX)
    expect(t.y).toBeCloseTo(0)
    expect(t.x).toBeCloseTo((800 - 1280 * t.scale) / 2)
  })

  it('keeps the point under the cursor fixed while zooming', () => {
    const before = toTransform(FIT, IMG, BOX)
    const px = 500
    const py = 120
    const imagePoint = { x: (px - before.x) / before.scale, y: (py - before.y) / before.scale }
    const view = zoomAt(FIT, 3, px, py, IMG, BOX)
    const after = toTransform(view, IMG, BOX)
    expect(after.x + imagePoint.x * after.scale).toBeCloseTo(px, 6)
    expect(after.y + imagePoint.y * after.scale).toBeCloseTo(py, 6)
  })

  it('never zooms out below fit or beyond 8 px per image px', () => {
    expect(zoomAt(FIT, 0.2, 10, 10, IMG, BOX).zoom).toBe(1)
    const huge = zoomAt(FIT, 1e6, 400, 200, IMG, BOX)
    expect(huge.zoom).toBeCloseTo(maxZoom(IMG, BOX))
    expect(toTransform(huge, IMG, BOX).scale).toBeCloseTo(8)
  })

  it('clamps panning so the image always covers the viewport', () => {
    const zoomed = { zoom: 4, cx: 0.5, cy: 0.5 }
    const farLeft = panBy(zoomed, 1e6, 0, IMG, BOX)
    expect(toTransform(farLeft, IMG, BOX).x).toBeCloseTo(0, 6)
    const farUp = panBy(zoomed, 0, 1e6, IMG, BOX)
    expect(toTransform(farUp, IMG, BOX).y).toBeCloseTo(0, 6)
    // at fit, the narrow axis stays centred whatever the pan
    expect(panBy(FIT, 300, 0, IMG, BOX)).toEqual(FIT)
  })

  it('shares a view between renditions of different pixel size', () => {
    const view = clampView({ zoom: 3, cx: 0.3, cy: 0.6 }, IMG, BOX)
    const large = { width: 1200, height: 900 }
    const a = toTransform(view, IMG, BOX)
    const b = toTransform(view, large, BOX)
    // the same image fraction lands on the same screen point
    expect(a.x + 0.3 * IMG.width * a.scale).toBeCloseTo(b.x + 0.3 * large.width * b.scale, 6)
  })

  it('computes the native (1:1) view', () => {
    expect(toTransform(nativeView(FIT, IMG, BOX), IMG, BOX).scale).toBeCloseTo(1)
  })
})
