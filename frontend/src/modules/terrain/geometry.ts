import type { CostModel, EN, Extent, MapRequest, PlannerName } from '../../api/types'

/** Calibrated defaults (see docs/terrain-navigation.md); mirrors the backend CostModel. */
export const DEFAULT_COST_MODEL: CostModel = {
  max_slope_deg: 30,
  slope_weight: 4,
  max_roughness_m: 0.3,
  roughness_weight: 3,
}

/** Stable identity of a map request (same request → same server-side map). */
export function requestKey(request: MapRequest | null): string | null {
  return request ? JSON.stringify(request) : null
}

/** Map a projected point to fractions of an extent (x → east, y → south, both 0..1). */
export function toFraction(extent: Extent, e: number, n: number): { x: number; y: number } {
  return {
    x: (e - extent.e_min) / (extent.e_max - extent.e_min),
    y: (extent.n_max - n) / (extent.n_max - extent.n_min),
  }
}

export function fromFraction(extent: Extent, x: number, y: number): EN {
  return {
    e: extent.e_min + x * (extent.e_max - extent.e_min),
    n: extent.n_max - y * (extent.n_max - extent.n_min),
  }
}

/** SVG polyline "x,y x,y" for points in an extent rendered at width × height. */
export function polyline(extent: Extent, points: [number, number][], width: number, height: number): string {
  return points
    .map(([e, n]) => {
      const f = toFraction(extent, e, n)
      return `${(f.x * width).toFixed(1)},${(f.y * height).toFixed(1)}`
    })
    .join(' ')
}

export function inside(extent: Extent, p: EN): boolean {
  return p.e >= extent.e_min && p.e <= extent.e_max && p.n >= extent.n_min && p.n <= extent.n_max
}

/**
 * Categorical series in fixed slot order (validated dark-mode palette: adjacent CVD ΔE ≥ 8.4,
 * normal-vision ΔE ≥ 19.8, ≥ 3:1 on the panel surface). Dijkstra is dashed because it usually
 * coincides with A*. The real drive is not a planner: neutral white with a halo.
 */
export const ROUTE_STYLE: Record<PlannerName | 'actual', { color: string; dash?: string; label: string }> = {
  astar: { color: '#3987e5', label: 'A*' },
  dijkstra: { color: '#d95926', dash: '6 5', label: 'Dijkstra' },
  theta_star: { color: '#199e70', label: 'Theta*' },
  rrt_star: { color: '#c98500', dash: '2 4', label: 'RRT*' },
  actual: { color: '#f2f0ea', label: "Rover's actual drive" },
}

export const PLANNER_ORDER: PlannerName[] = ['astar', 'dijkstra', 'theta_star', 'rrt_star']

/** Value of a piecewise-linear profile at distance d (null outside its range). */
export function profileAt(profile: [number, number][], d: number): number | null {
  if (profile.length === 0) return null
  const first = profile[0]!
  const last = profile[profile.length - 1]!
  if (d < first[0] || d > last[0]) return null
  for (let i = 1; i < profile.length; i++) {
    const [d1, z1] = profile[i]!
    const [d0, z0] = profile[i - 1]!
    if (d <= d1) return d1 === d0 ? z1 : z0 + ((z1 - z0) * (d - d0)) / (d1 - d0)
  }
  return last[1]
}
