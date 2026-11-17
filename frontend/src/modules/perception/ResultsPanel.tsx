import type { VisionAnalysis, VisionMethod } from '../../api/types'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { DataList } from '../../design-system/primitives'

const STAT_LABELS: Record<string, string> = {
  candidates: 'Candidates',
  score_median: 'Median score',
  radius_px_median: 'Median radius (px)',
  input_std: 'Contrast before (std)',
  output_std: 'Contrast after (std)',
  edge_pixel_fraction: 'Edge pixels',
  keypoints: 'Keypoints',
  grid_coverage: 'Grid coverage',
  capped: 'Limit reached',
}

function statLabel(key: string): string {
  const cls = /^class_(\d+)_share$/.exec(key)
  if (cls) return `Class ${cls[1]} share`
  return STAT_LABELS[key] ?? key.replace(/_/g, ' ')
}

function statValue(key: string, value: number | string): string {
  if (typeof value === 'string') return value
  if (key.endsWith('_share') || key === 'edge_pixel_fraction' || key === 'grid_coverage') {
    return `${(value * 100).toFixed(1)} %`
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

export function ResultsPanel({ analysis, method }: { analysis: VisionAnalysis; method: VisionMethod }) {
  const total = Object.values(analysis.timings_ms).reduce((a, b) => a + b, 0)
  return (
    <div className="rp">
      <div className="rp__badges">
        <ProvenanceBadge provenance={analysis.provenance} credit="Mars Explorer" />
        <span className="rp__kind">Algorithmic · not a model prediction</span>
      </div>

      <section className="rp__section">
        <h3 className="label">Results</h3>
        <DataList
          items={Object.entries(analysis.stats).map(([key, value]) => ({ label: statLabel(key), value: statValue(key, value) }))}
        />
      </section>

      {analysis.score_definition && (
        <section className="rp__section">
          <h3 className="label">Score definition</h3>
          <p className="rp__text">{analysis.score_definition}</p>
        </section>
      )}

      <section className="rp__section">
        <h3 className="label">Limitations</h3>
        <ul className="rp__limits">
          {analysis.limitations.map((limit) => (
            <li key={limit}>{limit}</li>
          ))}
        </ul>
      </section>

      <section className="rp__section">
        <h3 className="label">Run</h3>
        <DataList
          items={[
            ...Object.entries(analysis.timings_ms).map(([step, ms]) => ({ label: step.replace(/_/g, ' '), value: `${ms.toFixed(1)} ms` })),
            { label: 'Total', value: `${total.toFixed(1)} ms`, hint: 'Server-side compute time, excluding image decoding' },
            { label: 'Image', value: `${analysis.width} × ${analysis.height} px (${analysis.rendition})` },
            { label: 'Algorithm', value: `v${analysis.algorithm_version} · ${analysis.id.slice(0, 8)}`, hint: 'Cache key covers image, method, parameters and algorithm version' },
          ]}
        />
      </section>
      {method.experimental && <p className="rp__experimental">Experimental method — read the limitations before drawing conclusions.</p>}
    </div>
  )
}
