import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import type { Annotation, Evaluation, VisionAnalysis, VisionMethod } from '../../api/types'
import { useApi } from '../../api/useApi'
import { ErrorState, SkeletonBlock } from '../../design-system/primitives'
import { formatSol } from '../../lib/format'
import { FIT, type View } from '../explorer/zoom'
import { ZoomViewer, type ViewerLayer } from '../explorer/ZoomViewer'
import { EvaluationPanel } from './EvaluationPanel'
import { MatchView } from './MatchView'
import { ParamForm } from './ParamForm'
import { changedParams, defaultParams, type ParamValues } from './params'
import { ResultsPanel } from './ResultsPanel'

const CATEGORY_ORDER: VisionMethod['category'][] = ['detection', 'enhancement', 'structure', 'segmentation', 'features']
const CATEGORY_LABEL: Record<VisionMethod['category'], string> = {
  detection: 'Rock candidates',
  enhancement: 'Enhancement',
  structure: 'Structure',
  segmentation: 'Segmentation',
  features: 'Features',
}
const DEFAULT_METHOD = 'rocks_blob'

const message = (error: unknown) => (error instanceof ApiError ? error.message : String(error))

export function Workspace({ imageId }: { imageId: string }) {
  const navigate = useNavigate()
  const detail = useApi(`perception-detail:${imageId}`, (signal) => api.image(imageId, signal))
  const methods = useApi('vision-methods', api.visionMethods)
  const related = useApi(`perception-related:${imageId}`, (signal) => api.related(imageId, signal))

  const [methodName, setMethodName] = useState(DEFAULT_METHOD)
  const [paramsByMethod, setParamsByMethod] = useState<Record<string, ParamValues>>({})
  const [analysis, setAnalysis] = useState<VisionAnalysis | null>(null)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [tab, setTab] = useState<'analyze' | 'match'>('analyze')
  const [view, setView] = useState<View>(FIT)
  const [hiddenLayers, setHiddenLayers] = useState<Set<string>>(new Set())
  const [opacity, setOpacity] = useState(0.8)
  const [showDetections, setShowDetections] = useState(true)
  const [showAnnotations, setShowAnnotations] = useState(true)
  const [annotations, setAnnotations] = useState<Annotation[]>([])
  const [annotating, setAnnotating] = useState(false)
  const [annotationBusy, setAnnotationBusy] = useState(false)
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const latestRun = useRef(0)

  const methodList = useMemo(() => methods.state.data ?? [], [methods.state.data])
  const method = methodList.find((m) => m.name === methodName) ?? null
  const values = method ? (paramsByMethod[method.name] ?? defaultParams(method)) : {}

  const run = useCallback(
    async (spec: VisionMethod, params: ParamValues) => {
      const ticket = ++latestRun.current
      setRunning(true)
      setRunError(null)
      try {
        const result = await api.analyze(imageId, spec.name, changedParams(spec, params))
        if (ticket !== latestRun.current) return // a newer run superseded this one
        setAnalysis(result)
        setHiddenLayers(new Set())
      } catch (error) {
        if (ticket === latestRun.current) setRunError(message(error))
      } finally {
        if (ticket === latestRun.current) setRunning(false)
      }
    },
    [imageId],
  )

  // Score the current detector whenever the analysis or the set of marks changes. The effect
  // only synchronises with the server; "scoring…" is derived from whether the result is current.
  const evaluatedAnalysis = analysis && analysis.method === methodName ? analysis : null
  const scorable = Boolean(evaluatedAnalysis?.detections) && annotations.length > 0
  useEffect(() => {
    if (!evaluatedAnalysis?.detections || annotations.length === 0) return
    let cancelled = false
    api.evaluation(evaluatedAnalysis.id).then(
      (result) => !cancelled && setEvaluation(result),
      () => !cancelled && setEvaluation(null),
    )
    return () => {
      cancelled = true
    }
  }, [evaluatedAnalysis, annotations.length])

  // Load the user's annotations for this image once.
  useEffect(() => {
    const controller = new AbortController()
    api.annotations(imageId, controller.signal).then(setAnnotations, () => undefined)
    return () => controller.abort()
  }, [imageId])

  // First analysis with default parameters as soon as the catalogue is known.
  const started = useRef(false)
  useEffect(() => {
    if (started.current || !method) return
    started.current = true
    void run(method, defaultParams(method)) // nothing has been edited yet
  }, [method, run])

  const selectMethod = (spec: VisionMethod) => {
    setMethodName(spec.name)
    setTab('analyze')
    void run(spec, paramsByMethod[spec.name] ?? defaultParams(spec))
  }

  const addAnnotation = async (x: number, y: number) => {
    // Never drop a click: each mark is saved independently, even while others are in flight.
    try {
      const created = await api.addAnnotation(imageId, x, y)
      setAnnotations((current) => [...current, created])
    } catch (error) {
      setRunError(message(error))
    }
  }

  const removeAnnotations = async (targets: Annotation[]) => {
    if (!targets.length) return
    setAnnotationBusy(true)
    try {
      await Promise.all(targets.map((a) => api.deleteAnnotation(a.id)))
      const removed = new Set(targets.map((a) => a.id))
      setAnnotations((current) => current.filter((a) => !removed.has(a.id)))
    } catch (error) {
      setRunError(message(error))
    } finally {
      setAnnotationBusy(false)
    }
  }

  const image = detail.state.data
  const stereoPartner = related.state.data?.stereo?.local ?? null
  const current = evaluatedAnalysis

  if (detail.state.status === 'error') {
    return <ErrorState title="Image unavailable" message={detail.state.error.message} onRetry={detail.retry} />
  }
  if (methods.state.status === 'error') {
    return <ErrorState title="Perception methods unavailable" message={methods.state.error.message} onRetry={methods.retry} />
  }

  const layers: ViewerLayer[] = image
    ? [
        { src: image.preview_url, alt: `${image.camera.label}, sol ${image.sol}` },
        ...(current?.layers ?? [])
          .filter((layer) => !hiddenLayers.has(layer.name))
          .map((layer) => ({ src: layer.url, alt: layer.label, opacity })),
      ]
    : []

  return (
    <div className="pw">
      <header className="pw__bar">
        <button type="button" className="ds-button" onClick={() => navigate('/perception')}>
          ← Images
        </button>
        <div className="xd__title">
          {image && (
            <>
              <span className="mono xd__sol">SOL {formatSol(image.sol)}</span>
              <span className="xd__cam">{image.camera.label}</span>
            </>
          )}
        </div>
        <div className="pw__tabs" role="tablist" aria-label="Workspace mode">
          <button type="button" role="tab" aria-selected={tab === 'analyze'} className={tab === 'analyze' ? 'is-active' : ''} onClick={() => setTab('analyze')}>
            Analyze
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'match'}
            className={tab === 'match' ? 'is-active' : ''}
            onClick={() => setTab('match')}
            disabled={!stereoPartner}
            title={stereoPartner ? 'Match features with the other eye' : 'Needs the stereo partner stored locally (fetch it in Explorer)'}
          >
            Stereo match
          </button>
        </div>
        <Link className="pw__link" to={`/explorer/${encodeURIComponent(imageId)}`}>
          Open in Explorer
        </Link>
      </header>

      {tab === 'match' && image && stereoPartner ? (
        <MatchView left={image} right={stereoPartner} />
      ) : (
        <div className="pw__body">
          <nav className="pw__methods" aria-label="Methods">
            {methodList.length === 0 && <SkeletonBlock lines={8} />}
            {CATEGORY_ORDER.map((category) => {
              const inCategory = methodList.filter((m) => m.category === category)
              if (!inCategory.length) return null
              return (
                <div key={category} className="pw__group">
                  <h3 className="xf__legend">{CATEGORY_LABEL[category]}</h3>
                  {inCategory.map((spec) => (
                    <button
                      key={spec.name}
                      type="button"
                      className={`pw__method${spec.name === methodName ? ' is-active' : ''}`}
                      aria-current={spec.name === methodName}
                      onClick={() => selectMethod(spec)}
                    >
                      <span>{spec.title}</span>
                      {spec.experimental && <span className="pw__exp">experimental</span>}
                    </button>
                  ))}
                </div>
              )
            })}
          </nav>

          <div className="pw__viewer">
            {image ? (
              <ZoomViewer
                layers={layers}
                view={view}
                onViewChange={setView}
                label={image.camera.label}
                clickMode={annotating}
                onImageClick={annotating ? (x, y) => void addAnnotation(x, y) : undefined}
                overlay={(natural, scale) => {
                  const sx = current ? natural.width / current.width : 1
                  const sy = current ? natural.height / current.height : 1
                  const marker = 7 / scale
                  return (
                    <>
                      {showDetections &&
                        current?.detections?.map((d, i) => (
                          <circle key={i} className="pw__det" cx={d.x * sx} cy={d.y * sy} r={Math.max(d.r * sx, 3 / scale)} />
                        ))}
                      {showAnnotations &&
                        annotations.map((a) => {
                          const cx = a.x * natural.width
                          const cy = a.y * natural.height
                          return (
                            <g key={a.id} className="pw__ann">
                              <circle cx={cx} cy={cy} r={marker * 0.8} />
                              <line x1={cx - marker * 1.6} x2={cx - marker * 0.4} y1={cy} y2={cy} />
                              <line x1={cx + marker * 0.4} x2={cx + marker * 1.6} y1={cy} y2={cy} />
                              <line x1={cx} x2={cx} y1={cy - marker * 1.6} y2={cy - marker * 0.4} />
                              <line x1={cx} x2={cx} y1={cy + marker * 0.4} y2={cy + marker * 1.6} />
                            </g>
                          )
                        })}
                    </>
                  )
                }}
              >
                {running && <span className="pw__running mono">computing…</span>}
              </ZoomViewer>
            ) : (
              <SkeletonBlock lines={10} />
            )}
            <div className="pw__layers" aria-label="Layers">
              <span className="label">Layers</span>
              {current?.layers.map((layer) => (
                <label key={layer.name} className="pf__bool">
                  <input
                    type="checkbox"
                    checked={!hiddenLayers.has(layer.name)}
                    onChange={() =>
                      setHiddenLayers((hidden) => {
                        const next = new Set(hidden)
                        if (next.has(layer.name)) next.delete(layer.name)
                        else next.add(layer.name)
                        return next
                      })
                    }
                  />
                  <span>{layer.label}</span>
                </label>
              ))}
              {current?.detections && (
                <label className="pf__bool">
                  <input type="checkbox" checked={showDetections} onChange={(e) => setShowDetections(e.target.checked)} />
                  <span>Candidates ({current.detections.length})</span>
                </label>
              )}
              <label className="pf__bool">
                <input type="checkbox" checked={showAnnotations} onChange={(e) => setShowAnnotations(e.target.checked)} />
                <span>My marks ({annotations.length})</span>
              </label>
              {current && current.layers.length > 0 && (
                <label className="pw__opacity">
                  <span className="label">Overlay</span>
                  <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={(e) => setOpacity(Number(e.target.value))} aria-label="Overlay opacity" />
                </label>
              )}
            </div>
          </div>

          <aside className="pw__side" aria-label="Method, parameters and results">
            {method ? (
              <>
                <section className="pw__section">
                  <h2 className="pw__title">{method.title}</h2>
                  <p className="pw__summary">{method.summary}</p>
                  <ParamForm
                    method={method}
                    values={values}
                    disabled={running}
                    onChange={(next) => setParamsByMethod((all) => ({ ...all, [method.name]: next }))}
                    onReset={() => setParamsByMethod((all) => ({ ...all, [method.name]: defaultParams(method) }))}
                  />
                  <button type="button" className="ds-button xi__go pw__run" onClick={() => void run(method, values)} disabled={running}>
                    {running ? 'Running…' : 'Run'}
                  </button>
                  {runError && (
                    <p className="xi__error" role="alert">
                      {runError}
                    </p>
                  )}
                </section>
                {current && (
                  <section className="pw__section">
                    <ResultsPanel analysis={current} method={method} />
                  </section>
                )}
                {method.produces_detections && (
                  <section className="pw__section">
                    <h3 className="label">Evaluate against your marks</h3>
                    <EvaluationPanel
                      annotations={annotations}
                      annotating={annotating}
                      onToggleAnnotating={() => setAnnotating((v) => !v)}
                      onUndo={() => void removeAnnotations(annotations.slice(-1))}
                      onClear={() => void removeAnnotations(annotations)}
                      evaluation={scorable && evaluation?.analysis_id === current?.id ? evaluation : null}
                      evaluating={scorable && evaluation?.analysis_id !== current?.id}
                      busy={annotationBusy}
                    />
                  </section>
                )}
              </>
            ) : (
              <SkeletonBlock lines={12} />
            )}
          </aside>
        </div>
      )}
    </div>
  )
}
