import { useState } from 'react'
import type { Annotation, Evaluation } from '../../api/types'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { DataList } from '../../design-system/primitives'

interface EvaluationPanelProps {
  annotations: Annotation[]
  annotating: boolean
  onToggleAnnotating: () => void
  onUndo: () => void
  onClear: () => void
  evaluation: Evaluation | null
  evaluating: boolean
  busy: boolean
}

const pct = (value: number | null) => (value === null ? '—' : `${(value * 100).toFixed(0)} %`)

export function EvaluationPanel({
  annotations,
  annotating,
  onToggleAnnotating,
  onUndo,
  onClear,
  evaluation,
  evaluating,
  busy,
}: EvaluationPanelProps) {
  const [confirmClear, setConfirmClear] = useState(false)
  return (
    <div className="ev">
      <p className="ev__intro">
        There is no labelled ground truth for these images. Mark every rock you consider an obstacle candidate; the
        detector is then scored against <em>your</em> interpretation.
      </p>
      <div className="ev__actions">
        <button type="button" className={`ds-button${annotating ? ' is-on' : ''}`} aria-pressed={annotating} onClick={onToggleAnnotating}>
          {annotating ? 'Stop marking' : 'Mark rocks'}
        </button>
        <button type="button" className="ds-button" onClick={onUndo} disabled={!annotations.length || busy}>
          Undo last
        </button>
        {confirmClear ? (
          <button
            type="button"
            className="ds-button ev__danger"
            onClick={() => {
              setConfirmClear(false)
              onClear()
            }}
            disabled={busy}
          >
            Confirm: delete {annotations.length}
          </button>
        ) : (
          <button type="button" className="ds-button" onClick={() => setConfirmClear(true)} disabled={!annotations.length || busy}>
            Clear all
          </button>
        )}
      </div>
      <div className="ev__count">
        <span className="mono">{annotations.length}</span> marked
        <ProvenanceBadge provenance="user_generated" />
      </div>
      {annotating && <p className="ev__hint">Click on the image to mark a rock centre. Drag still pans; scroll zooms.</p>}

      {annotations.length > 0 &&
        (evaluation ? (
          <>
            <div className="ev__metrics" aria-label="Evaluation against your annotations">
              <div>
                <span className="label">Precision</span>
                <strong className="mono">{pct(evaluation.precision)}</strong>
              </div>
              <div>
                <span className="label">Recall</span>
                <strong className="mono">{pct(evaluation.recall)}</strong>
              </div>
              <div>
                <span className="label">F1</span>
                <strong className="mono">{pct(evaluation.f1)}</strong>
              </div>
            </div>
            <DataList
              items={[
                { label: 'Matched (TP)', value: evaluation.true_positives, hint: 'Candidates matching one of your marks' },
                { label: 'Extra (FP)', value: evaluation.false_positives, hint: 'Candidates with no mark nearby' },
                { label: 'Missed (FN)', value: evaluation.false_negatives, hint: 'Marks with no candidate nearby' },
                { label: 'Tolerance', value: `≥ ${evaluation.tolerance_px} px`, hint: evaluation.matching },
              ]}
            />
            <ul className="ev__caveats">
              {evaluation.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </>
        ) : (
          <p className="ev__hint">{evaluating ? 'Scoring…' : 'Run a detector to score it against your marks.'}</p>
        ))}
    </div>
  )
}
