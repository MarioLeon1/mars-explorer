import type { ParamSpec, VisionMethod } from '../../api/types'
import { coerceNumber, formatParam, type ParamValues } from './params'

interface ParamFormProps {
  method: VisionMethod
  values: ParamValues
  onChange: (values: ParamValues) => void
  onReset: () => void
  disabled?: boolean
}

function ParamControl({
  spec,
  value,
  onChange,
  disabled,
}: {
  spec: ParamSpec
  value: ParamValues[string]
  onChange: (value: ParamValues[string]) => void
  disabled?: boolean
}) {
  const id = `param-${spec.name}`
  if (spec.type === 'bool') {
    return (
      <label className="pf__bool" htmlFor={id} title={spec.help}>
        <input id={id} type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
        <span>{spec.label}</span>
      </label>
    )
  }
  if (spec.type === 'choice') {
    return (
      <fieldset className="pf__choice" title={spec.help}>
        <legend className="pf__label">{spec.label}</legend>
        <div role="radiogroup" aria-label={spec.label}>
          {spec.choices.map((choice) => (
            <button
              key={choice}
              type="button"
              role="radio"
              aria-checked={value === choice}
              className={value === choice ? 'is-active' : ''}
              disabled={disabled}
              onClick={() => onChange(choice)}
            >
              {choice}
            </button>
          ))}
        </div>
      </fieldset>
    )
  }
  const numeric = typeof value === 'number' ? value : Number(spec.default)
  return (
    <div className="pf__num" title={spec.help}>
      <label className="pf__label" htmlFor={id}>
        {spec.label}
        <span className="pf__value mono">{formatParam(spec, numeric)}</span>
      </label>
      <input
        id={id}
        type="range"
        min={spec.min ?? undefined}
        max={spec.max ?? undefined}
        step={spec.step ?? (spec.type === 'int' ? 1 : 0.01)}
        value={numeric}
        disabled={disabled}
        onChange={(e) => {
          const next = coerceNumber(spec, e.target.value)
          if (next !== null) onChange(next)
        }}
      />
      <p className="pf__help">{spec.help}</p>
    </div>
  )
}

export function ParamForm({ method, values, onChange, onReset, disabled }: ParamFormProps) {
  const isDefault = method.params.every((p) => values[p.name] === p.default)
  return (
    <div className="pf">
      {method.params.map((spec) => (
        <ParamControl
          key={spec.name}
          spec={spec}
          value={values[spec.name] ?? spec.default}
          disabled={disabled}
          onChange={(value) => onChange({ ...values, [spec.name]: value })}
        />
      ))}
      {method.params.length > 0 && (
        <button type="button" className="pf__reset" onClick={onReset} disabled={isDefault || disabled}>
          Reset to defaults
        </button>
      )}
    </div>
  )
}
