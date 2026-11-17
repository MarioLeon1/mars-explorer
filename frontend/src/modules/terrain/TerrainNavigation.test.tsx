import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DrivePath, Plan, PlannedRoute, TerrainMap } from '../../api/types'
import { ElevationProfile } from './ElevationProfile'
import { RouteResults } from './RouteResults'
import { TerrainNavigation } from './TerrainNavigation'

const extent = { e_min: 1000, e_max: 1800, n_min: 5000, n_max: 5800 }
const status = {
  available: true,
  rows: 548,
  cols: 1480,
  cell_m: 1,
  extent: { e_min: 0, e_max: 14800, n_min: 0, n_max: 5480 },
  bounds_deg: { lon_min: 0, lon_max: 1, lat_min: 0, lat_max: 1 },
  validation: { waypoints: 708, inside: 708, compared: 708, median_offset_m: 0.002, p95_abs_offset_m: 0.114 },
  source: { name: 'PLACES', url: 'https://pds', credit: 'NASA/JPL-Caltech' },
  provenance: 'real_observation',
  notes: [],
  how_to_get: null,
}
const drives: DrivePath[] = [
  { index: 0, sol: 1965, from_rmc: null, to_rmc: null, length_m: 29, points: [[1200, 5400], [1220, 5410]] },
  { index: 1, sol: 2022, from_rmc: null, to_rmc: null, length_m: 22, points: [[1220, 5410], [1240, 5420]] },
]
const terrainMap: TerrainMap = {
  id: 'map1',
  center: { e: 1400, n: 5400 },
  size_m: 800,
  cell_m: 3,
  grid: [267, 267],
  extent,
  cost_model: {},
  layers: [
    { name: 'hillshade', label: 'Shaded relief', url: '/h.png', legend: [] },
    { name: 'risk', label: 'Risk', url: '/r.png', legend: [{ label: 'low', color: '#5fbf7a' }, { label: 'impassable', color: '#e5534b' }] },
  ],
  stats: { slope_p50_deg: 8, slope_p95_deg: 18, slope_max_deg: 40, roughness_p95_m: 0.1, elevation_min_m: -2000, elevation_max_m: -1900, risk_fraction: { low: 0.8, moderate: 0.15, high: 0.04, impassable: 0.01 } },
  drives_in_view: drives,
  provenance: 'derived',
  assumptions: ['Assumption A'],
  limitations: ['1 m posts miss small rocks'],
}

function route(planner: PlannedRoute['planner'], cost: number, extra: Partial<PlannedRoute> = {}): PlannedRoute {
  return {
    planner,
    title: { astar: 'A*', dijkstra: 'Dijkstra', theta_star: 'Theta*', rrt_star: 'RRT*', actual: "Rover's actual drive" }[planner],
    kind: planner === 'rrt_star' ? 'randomized' : planner === 'actual' ? 'real_observation' : 'deterministic',
    found: true,
    reason: null,
    points: [[1200, 5400], [1240, 5420]],
    metrics: {
      feasible: true, length_m: 100, impassable_m: 0, cost, cost_distance: 100, cost_slope: cost - 100, cost_roughness: 0,
      max_slope_deg: 10, mean_slope_deg: 5, max_roughness_m: 0.05, elevation_gain_m: 2, elevation_loss_m: 1,
      min_clearance_m: 12, profile: [[0, -1950], [50, -1948], [100, -1949]],
    },
    expanded: 100,
    elapsed_ms: 12,
    extra: {},
    ...extra,
  }
}

const plan: Plan = {
  map: terrainMap,
  start: { e: 1200, n: 5400 },
  goal: { e: 1240, n: 5420 },
  snapped: false,
  routes: [route('astar', 140), route('dijkstra', 140, { expanded: 800 }), route('theta_star', 138), route('rrt_star', 0, { found: false, reason: 'goal not reached within 3000 iterations (seed 42)', metrics: null })],
  actual: route('actual', 253),
  best: 'theta_star',
  explanation: ['Theta* has the lowest total cost (138).', "The rover's real drive path scores 253."],
  provenance: 'derived',
}

const json = (body: unknown, code = 200) => new Response(JSON.stringify(body), { status: code })

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('TerrainNavigation', () => {
  it('explains how to download the DEM when it is missing', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ ...status, available: false, how_to_get: 'cd backend; uv run mars-terrain fetch' })))
    render(<MemoryRouter><TerrainNavigation /></MemoryRouter>)
    expect(await screen.findByText('The orbital elevation model is not downloaded yet')).toBeInTheDocument()
    expect(screen.getByText('cd backend; uv run mars-terrain fetch')).toBeInTheDocument()
  })

  it('opens at the latest real position, replans real drives and shows the comparison', async () => {
    const posts: { path: string; body: Record<string, unknown> }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = new URL(String(input), 'http://localhost')
        if (init?.method === 'POST') posts.push({ path: url.pathname, body: JSON.parse(String(init.body)) })
        if (url.pathname === '/api/terrain/status') return json(status)
        if (url.pathname === '/api/terrain/drives') return json(drives)
        if (url.pathname === '/api/terrain/maps') return json(terrainMap)
        if (url.pathname === '/api/navigation/plans') return json(plan)
        return json({ error: { code: 'not_found', message: url.pathname } }, 404)
      }),
    )
    const user = userEvent.setup()
    render(<MemoryRouter><TerrainNavigation /></MemoryRouter>)

    await waitFor(() => expect(posts.find((p) => p.path === '/api/terrain/maps')).toBeDefined())
    expect(posts[0]!.body).toMatchObject({ center: { e: 1240, n: 5420 }, size_m: 800 }) // end of latest drive
    expect(screen.getByRole('button', { name: 'Plan routes' })).toBeDisabled() // no start/goal yet
    expect(await screen.findByText(/708 real localizations/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Load these drives' }))
    await waitFor(() => expect(posts.some((p) => Array.isArray(p.body.drives))).toBe(true))
    await user.click(screen.getByRole('button', { name: 'Plan routes' }))

    const table = await screen.findByRole('table', { name: 'Route comparison' })
    const best = within(table).getByRole('row', { name: /Theta\*.*best/ })
    expect(best).toHaveClass('is-best')
    expect(within(table).getByText('goal not reached within 3000 iterations (seed 42)')).toBeInTheDocument()
    expect(within(table).getByRole('row', { name: /Rover's actual drive/ })).toBeInTheDocument()
    expect(screen.getByText('Theta* has the lowest total cost (138).')).toBeInTheDocument()
    expect(screen.getByText(/no language model is involved/)).toBeInTheDocument()
    const planPost = posts.find((p) => p.path === '/api/navigation/plans')!
    expect(planPost.body).toMatchObject({ map: { drives: [0, 1] }, rrt_seed: 42, planners: ['astar', 'dijkstra', 'theta_star', 'rrt_star'] })
  })
})

describe('RouteResults', () => {
  it('flags routes that cross impassable cells instead of hiding them', () => {
    const blocked = route('actual', 0)
    blocked.metrics = { ...blocked.metrics!, feasible: false, cost: null, impassable_m: 14 }
    render(<RouteResults plan={{ ...plan, actual: blocked }} />)
    expect(screen.getByText('blocked 14 m')).toBeInTheDocument()
    expect(screen.getByText('DERIVED')).toBeInTheDocument()
    expect(screen.getByText('REAL')).toBeInTheDocument()
  })
})

describe('ElevationProfile', () => {
  it('draws one line per route with a legend', () => {
    const { container } = render(
      <ElevationProfile
        series={[
          { key: 'a', label: 'A*', color: '#3987e5', profile: [[0, -1950], [100, -1940]] },
          { key: 'b', label: 'Actual', color: '#fff', profile: [[0, -1950], [150, -1945]] },
        ]}
      />,
    )
    expect(screen.getByRole('list', { name: 'Profile legend' })).toHaveTextContent('A*Actual')
    expect(container.querySelectorAll('polyline')).toHaveLength(2)
  })
})
