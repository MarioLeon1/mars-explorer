import type { Provenance } from '../api/types'

const LABELS: Record<Provenance, { short: string; title: string }> = {
  real_observation: { short: 'REAL', title: 'Real observation published by NASA/JPL or partners' },
  derived: { short: 'DERIVED', title: 'Computed by Mars Explorer from real observations' },
  simulated: { short: 'SIMULATED', title: 'Simulated — not a mission measurement' },
  user_generated: { short: 'USER', title: 'Created by the user' },
}

interface ProvenanceBadgeProps {
  provenance: Provenance
  /** Credit line, e.g. "NASA/JPL-Caltech". */
  credit?: string | null
}

export function ProvenanceBadge({ provenance, credit }: ProvenanceBadgeProps) {
  const { short, title } = LABELS[provenance]
  return (
    <span className={`ds-prov ds-prov--${provenance}`} title={title}>
      <span className="ds-prov__dot" aria-hidden="true" />
      <span className="ds-prov__kind">{short}</span>
      {credit && <span className="ds-prov__credit">{credit}</span>}
      <span className="visually-hidden">{` — ${title}`}</span>
    </span>
  )
}
