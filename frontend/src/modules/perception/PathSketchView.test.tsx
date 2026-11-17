import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ImageDetail, PathSketch } from '../../api/types'
import { PathSketchView } from './PathSketchView'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const image = {
  image_id: 'NLF_TEST',
  sol: 2022,
  camera: { instrument: 'NAVCAM_LEFT', group: 'navcam', label: 'Navigation Camera — left (Navcam)' },
  preview_url: '/api/images/NLF_TEST/file/large',
} as unknown as ImageDetail

const sketch: PathSketch = {
  image_id: 'NLF_TEST',
  width: 1200,
  height: 900,
  found: true,
  reason: null,
  path: [
    [600, 860],
    [520, 600],
    [700, 300],
  ],
  start: [600, 860],
  goal: [700, 300],
  horizon: 0.12,
  horizon_auto: true,
  detector: 'blobs',
  obstacles: [{ x: 640, y: 560, r: 20 }],
  cost_layer: 'data:image/png;base64,AAAA',
  metrics: {
    length_px: 640,
    straight_px: 570,
    detour_pct: 12.3,
    min_clearance_px: 18,
    obstacles: 1,
    blocking_straight_line: 1,
    grid: [96, 128],
    cell_px: 9.4,
    elapsed_ms: 190,
  },
  explanation: ['The straight line from A to B crosses 1 candidate(s); the path bends around them.'],
  assumptions: ['Rock candidates are treated as obstacles.'],
  limitations: ['Not a drivable route.'],
  kind: 'image_space_sketch',
  method: 'algorithmic',
  provenance: 'derived',
}

afterEach(() => vi.unstubAllGlobals())

describe('PathSketchView', () => {
  it('is labelled as an image-space illustration and asks for a goal first', () => {
    vi.stubGlobal('fetch', vi.fn())
    render(<PathSketchView image={image} />)
    expect(screen.getByText('IMAGE-SPACE SKETCH · not a drivable route')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Place the goal (B) first' })).toBeDisabled()
    expect(screen.getByText('Click the image to place the goal (B).')).toBeInTheDocument()
  })

  it('plans with the chosen settings and explains the result', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        bodies.push(JSON.parse(String(init?.body)))
        return json(sketch)
      }),
    )
    render(<PathSketchView image={image} />)
    await userEvent.selectOptions(screen.getByRole('combobox'), 'contours')
    await userEvent.click(screen.getByRole('button', { name: 'Goal at centre' }))
    expect(await screen.findByText('Why this path')).toBeInTheDocument()
    expect(bodies).toEqual([
      {
        image_id: 'NLF_TEST',
        goal: { x: 0.5, y: 0.55 },
        detector: 'contours',
        clearance: 1.6,
        roughness_weight: 2,
        horizon: null,
      },
    ])
    expect(screen.getByText('ALGORITHMIC · IMAGE SPACE')).toBeInTheDocument()
    expect(screen.getByText('12.3 %')).toBeInTheDocument()
    expect(screen.getByText('1 · 1 on straight line')).toBeInTheDocument()
    expect(screen.getByText(/crosses 1 candidate/)).toBeInTheDocument()
    expect(screen.getByText('Not a drivable route.')).toBeInTheDocument()
  })

  it('sends a manual horizon and shows refusals', async () => {
    const bodies: { horizon: number | null }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        bodies.push(JSON.parse(String(init?.body)))
        return json({ ...sketch, found: false, reason: 'the goal is inside an obstacle', path: [], horizon_auto: false })
      }),
    )
    render(<PathSketchView image={image} />)
    await userEvent.click(screen.getByRole('checkbox', { name: 'Estimate horizon automatically' }))
    await userEvent.click(screen.getByRole('button', { name: 'Goal at centre' }))
    expect(await screen.findByText('No path: the goal is inside an obstacle')).toBeInTheDocument()
    expect(bodies[0]?.horizon).toBe(0.3)
  })
})
