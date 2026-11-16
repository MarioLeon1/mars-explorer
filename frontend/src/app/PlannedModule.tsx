import { Panel } from '../design-system/Panel'
import type { ModuleDef } from './modules'

/** Honest placeholder for modules not built yet: says what will exist, shows nothing fake. */
export function PlannedModule({ module }: { module: ModuleDef }) {
  return (
    <div className="planned">
      <Panel title={module.label} meta={<span className="planned__phase mono">PHASE {module.phase}</span>}>
        <p className="planned__lead">{module.description}</p>
        <p className="planned__status">Not built yet. Planned scope:</p>
        <ul className="planned__list">
          {module.plan.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Panel>
    </div>
  )
}
