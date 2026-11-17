import type { Plan, PlannedRoute } from '../../api/types'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { formatNumber } from '../../lib/format'
import { ROUTE_STYLE } from './geometry'

function Swatch({ route }: { route: PlannedRoute }) {
  const style = ROUTE_STYLE[route.planner]
  return (
    <svg width="22" height="8" aria-hidden="true">
      <line x1="0" x2="22" y1="4" y2="4" stroke={style.color} strokeWidth="2.5" strokeDasharray={style.dash} />
    </svg>
  )
}

const m = (value: number | null | undefined, digits = 0, unit = '') =>
  value === null || value === undefined ? '—' : `${formatNumber(value, digits)}${unit}`

export function RouteResults({ plan }: { plan: Plan }) {
  const rows = plan.actual ? [...plan.routes, plan.actual] : plan.routes
  return (
    <div className="tn-results">
      <div className="tn-table-wrap">
        <table className="ph__table tn-table">
          <caption className="visually-hidden">Route comparison</caption>
          <thead>
            <tr>
              <th scope="col">Route</th>
              <th scope="col" title="Length along the route">Length</th>
              <th scope="col" title="Total cost under the cost model (lower is better)">Cost</th>
              <th scope="col" title="Steepest slope crossed">Max°</th>
              <th scope="col" title="Search nodes expanded / RRT* tree nodes (hover for compute time)">Nodes</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((route) => (
              <tr key={route.planner} className={route.planner === plan.best ? 'is-best' : ''}>
                <th scope="row">
                  <span className="tn-route-name">
                    <Swatch route={route} />
                    {route.title}
                    {route.planner === plan.best && <span className="tn-best">best</span>}
                  </span>
                </th>
                {route.found && route.metrics ? (
                  <>
                    <td className="mono">{m(route.metrics.length_m, 0, ' m')}</td>
                    <td className="mono">{route.metrics.cost === null ? `blocked ${m(route.metrics.impassable_m, 0, ' m')}` : m(route.metrics.cost)}</td>
                    <td className="mono">{m(route.metrics.max_slope_deg, 1)}</td>
                    <td className="mono" title={route.kind === 'real_observation' ? undefined : `${formatNumber(route.elapsed_ms)} ms`}>
                      {route.kind === 'real_observation' ? '—' : formatNumber(route.expanded)}
                    </td>
                  </>
                ) : (
                  <td colSpan={4} className="tn-fail">
                    {route.reason}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="tn-badges">
        <ProvenanceBadge provenance="derived" credit="routes & costs" />
        {plan.actual && <ProvenanceBadge provenance="real_observation" credit="drive path · JPL" />}
      </div>

      <section className="tn-explain" aria-label="Why this route">
        <h3 className="label">Why this route</h3>
        <ol>
          {plan.explanation.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ol>
        <p className="tn-muted">Generated from the metrics above by fixed rules — no language model is involved in planning or explaining.</p>
      </section>

      {plan.routes.some((r) => r.metrics) && (
        <details className="tn-details">
          <summary>Cost breakdown and clearance</summary>
          <table className="ph__table tn-table">
            <thead>
              <tr>
                <th scope="col">Route</th>
                <th scope="col">Distance</th>
                <th scope="col">Slope</th>
                <th scope="col">Rough.</th>
                <th scope="col" title="Closest approach to an impassable cell">Clear.</th>
                <th scope="col" title="Compute time">ms</th>
              </tr>
            </thead>
            <tbody>
              {rows
                .filter((r) => r.metrics)
                .map((r) => (
                  <tr key={r.planner}>
                    <th scope="row">{r.title}</th>
                    <td className="mono">{m(r.metrics!.cost_distance)}</td>
                    <td className="mono">{m(r.metrics!.cost_slope)}</td>
                    <td className="mono">{m(r.metrics!.cost_roughness)}</td>
                    <td className="mono">{r.metrics!.min_clearance_m === null ? '∞' : m(r.metrics!.min_clearance_m, 0, ' m')}</td>
                    <td className="mono">{r.kind === 'real_observation' ? '—' : m(r.elapsed_ms)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  )
}
