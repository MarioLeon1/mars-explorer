import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import type { Benchmark } from '../../api/types'
import { Panel } from '../../design-system/Panel'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { ImageGrid } from '../explorer/ImageGrid'

const PRESETS: { label: string; cameras: string[] }[] = [
  { label: 'Navcam', cameras: ['NAVCAM_LEFT', 'NAVCAM_RIGHT'] },
  { label: 'Hazcams', cameras: ['FRONT_HAZCAM_LEFT_A', 'FRONT_HAZCAM_RIGHT_A', 'REAR_HAZCAM_LEFT', 'REAR_HAZCAM_RIGHT'] },
  { label: 'Mastcam-Z', cameras: ['MCZ_LEFT', 'MCZ_RIGHT'] },
  { label: 'All', cameras: [] },
]
const BENCHMARK_CAMERAS = ['NAVCAM_LEFT', 'NAVCAM_RIGHT', 'FRONT_HAZCAM_LEFT_A', 'FRONT_HAZCAM_RIGHT_A', 'REAR_HAZCAM_LEFT']

const num = (v: number | null | undefined, digits = 0) => (v === null || v === undefined ? '—' : v.toFixed(digits))
const pct = (v: number | null) => (v === null ? '—' : `${(v * 100).toFixed(0)} %`)

function BenchmarkPanel() {
  const [report, setReport] = useState<Benchmark | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setRunning(true)
    setError(null)
    try {
      setReport(await api.benchmark(BENCHMARK_CAMERAS, 40))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <Panel title="Detector benchmark" meta={report && <ProvenanceBadge provenance="derived" credit="Mars Explorer" />}>
      <p className="ph__text">
        Runs both rock-candidate detectors with default parameters on up to 40 stored Navcam/Hazcam images: speed,
        number of candidates, agreement between methods, and precision/recall on images you annotated.
      </p>
      <button type="button" className="ds-button xi__go" onClick={run} disabled={running}>
        {running ? 'Running… (a few seconds)' : report ? 'Run again' : 'Run benchmark'}
      </button>
      {error && <p className="xi__error">{error}</p>}
      {report && (
        <>
          <div className="ph__table-wrap">
            <table className="ph__table">
              <caption className="visually-hidden">Benchmark results per detector</caption>
              <thead>
                <tr>
                  <th scope="col">Detector</th>
                  <th scope="col" title="Median runtime per image">ms</th>
                  <th scope="col" title="Median candidates per image">Cand.</th>
                  <th scope="col" title="Precision on annotated images">P</th>
                  <th scope="col" title="Recall on annotated images">R</th>
                </tr>
              </thead>
              <tbody>
                {report.methods.map((m) => (
                  <tr key={m.method}>
                    <th scope="row">{m.title.replace('Rock candidates — ', '')}</th>
                    <td className="mono">{num(m.runtime_ms?.median, 1)}</td>
                    <td className="mono">{num(m.candidates?.median)}</td>
                    <td className="mono">{pct(m.precision)}</td>
                    <td className="mono">{pct(m.recall)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="ph__text mono">
            {report.images} images · {report.methods[0]?.annotated_images ?? 0} annotated · agreement between detectors (F1
            median): {num(report.agreement_f1?.median, 2)}
          </p>
          <ul className="rp__limits">
            {report.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  )
}

export function PerceptionHome() {
  const navigate = useNavigate()
  const [preset, setPreset] = useState(0)
  const cameras = PRESETS[preset]?.cameras ?? []

  return (
    <div className="ph">
      <div className="ph__side">
        <Panel title="Perception lab">
          <p className="ph__lead">Classical computer vision on real, uncalibrated raw images.</p>
          <ul className="ph__list">
            <li>Every result is <strong>derived</strong> data from a named algorithm, with its parameters, timings and limitations.</li>
            <li>Rock “candidates” are image regions that look like compact objects, not confirmed rocks. Sizes are pixels, never metres.</li>
            <li>Mark rocks yourself to measure each detector’s precision and recall against your interpretation.</li>
          </ul>
        </Panel>
        <BenchmarkPanel />
      </div>
      <div className="ph__main">
        <div className="ph__presets" role="radiogroup" aria-label="Camera preset">
          <span className="label">Choose an image</span>
          {PRESETS.map((p, i) => (
            <button key={p.label} type="button" role="radio" aria-checked={preset === i} className={preset === i ? 'is-active' : ''} onClick={() => setPreset(i)}>
              {p.label}
            </button>
          ))}
        </div>
        <ImageGrid
          filters={cameras.length ? { cameras } : {}}
          dataVersion={0}
          onOpen={(id) => navigate(`/perception/${encodeURIComponent(id)}`)}
          onClearFilters={() => setPreset(PRESETS.length - 1)}
        />
      </div>
    </div>
  )
}
