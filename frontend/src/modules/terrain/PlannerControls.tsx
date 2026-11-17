import type { CostModel, PlannerName } from '../../api/types'
import { DEFAULT_COST_MODEL, PLANNER_ORDER, ROUTE_STYLE } from './geometry'

const COST_FIELDS: {
  key: keyof CostModel
  label: string
  min: number
  max: number
  step: number
  unit: string
  help: string
}[] = [
  { key: 'max_slope_deg', label: 'Max slope', min: 5, max: 45, step: 1, unit: '°', help: 'Steeper cells are impassable.' },
  { key: 'slope_weight', label: 'Slope weight', min: 0, max: 20, step: 0.5, unit: '', help: 'Penalty at the limit (quadratic).' },
  { key: 'max_roughness_m', label: 'Max roughness', min: 0.05, max: 2, step: 0.05, unit: ' m', help: 'Rougher cells are impassable.' },
  { key: 'roughness_weight', label: 'Roughness weight', min: 0, max: 20, step: 0.5, unit: '', help: 'Penalty at the limit (quadratic).' },
]

const PLANNER_HELP: Record<PlannerName, string> = {
  astar: 'Optimal on the 8-connected grid; heuristic prunes the search.',
  dijkstra: 'Optimal, no heuristic: same cost as A*, more work.',
  theta_star: 'Any-angle: straight segments in line of sight.',
  rrt_star: 'Sampling-based, randomised (seeded).',
}

interface PlannerControlsProps {
  costModel: CostModel
  onCostModel: (model: CostModel) => void
  planners: PlannerName[]
  onPlanners: (planners: PlannerName[]) => void
  seed: number
  onSeed: (seed: number) => void
  iterations: number
  onIterations: (iterations: number) => void
  running: boolean
  canRun: boolean
  onRun: () => void
}

export function PlannerControls(props: PlannerControlsProps) {
  const { costModel, planners } = props
  const toggle = (name: PlannerName) =>
    props.onPlanners(planners.includes(name) ? planners.filter((p) => p !== name) : PLANNER_ORDER.filter((p) => p === name || planners.includes(p)))
  const isDefault = COST_FIELDS.every((f) => costModel[f.key] === DEFAULT_COST_MODEL[f.key])

  return (
    <div className="tn-controls">
      <fieldset className="tn-fieldset">
        <legend className="label">Cost model (assumptions)</legend>
        {COST_FIELDS.map((field) => (
          <div key={field.key} className="pf__num" title={field.help}>
            <label className="pf__label" htmlFor={`cm-${field.key}`}>
              {field.label}
              <span className="pf__value mono">
                {costModel[field.key]}
                {field.unit}
              </span>
            </label>
            <input
              id={`cm-${field.key}`}
              type="range"
              min={field.min}
              max={field.max}
              step={field.step}
              value={costModel[field.key]}
              onChange={(e) => props.onCostModel({ ...costModel, [field.key]: Number(e.target.value) })}
            />
          </div>
        ))}
        <button type="button" className="pf__reset" disabled={isDefault} onClick={() => props.onCostModel(DEFAULT_COST_MODEL)}>
          Reset to calibrated defaults
        </button>
      </fieldset>

      <fieldset className="tn-fieldset">
        <legend className="label">Planners</legend>
        {PLANNER_ORDER.map((name) => (
          <label key={name} className="tn-planner" title={PLANNER_HELP[name]}>
            <input type="checkbox" checked={planners.includes(name)} onChange={() => toggle(name)} />
            <svg width="22" height="8" aria-hidden="true">
              <line x1="0" x2="22" y1="4" y2="4" stroke={ROUTE_STYLE[name].color} strokeWidth="2.5" strokeDasharray={ROUTE_STYLE[name].dash} />
            </svg>
            <span>{ROUTE_STYLE[name].label}</span>
            <small>{PLANNER_HELP[name]}</small>
          </label>
        ))}
        {planners.includes('rrt_star') && (
          <div className="xf__pair">
            <label className="xf__field">
              <span className="label">RRT* seed</span>
              <input inputMode="numeric" value={props.seed} onChange={(e) => props.onSeed(Math.max(0, Math.floor(Number(e.target.value) || 0)))} />
            </label>
            <label className="xf__field">
              <span className="label">Iterations</span>
              <input
                inputMode="numeric"
                value={props.iterations}
                onChange={(e) => props.onIterations(Math.min(10000, Math.max(200, Math.floor(Number(e.target.value) || 200))))}
              />
            </label>
          </div>
        )}
      </fieldset>

      <button type="button" className="ds-button xi__go tn-run" onClick={props.onRun} disabled={!props.canRun || props.running || planners.length === 0}>
        {props.running ? 'Planning…' : 'Plan routes'}
      </button>
    </div>
  )
}
