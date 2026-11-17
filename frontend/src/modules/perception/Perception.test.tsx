import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Evaluation, ImageSummary, VisionAnalysis, VisionMethod } from '../../api/types'
import { EvaluationPanel } from './EvaluationPanel'
import { ParamForm } from './ParamForm'
import { Perception } from './Perception'

const image: ImageSummary = {
  image_id: 'NLG_A',
  sol: 2022,
  camera: { instrument: 'NAVCAM_LEFT', group: 'navcam', label: 'Navcam left' },
  sample_type: 'Full',
  date_taken_utc: null,
  date_taken_mars: null,
  lmst: null,
  site: null,
  drive: null,
  width: 1200,
  height: 900,
  thumb_url: '/api/images/NLG_A/file/small',
  preview_url: '/api/images/NLG_A/file/large',
  credit: 'NASA/JPL-Caltech',
  provenance: 'real_observation',
}

const blob: VisionMethod = {
  name: 'rocks_blob',
  title: 'Rock candidates — scale-space blobs',
  category: 'detection',
  kind: 'algorithmic',
  summary: 'DoG blobs',
  params: [
    { name: 'min_radius', label: 'Min radius (px)', type: 'float', default: 6, help: 'smallest', min: 2, max: 60, step: 1, choices: [] },
    { name: 'polarity', label: 'Polarity', type: 'choice', default: 'both', help: '', min: null, max: null, step: null, choices: ['both', 'bright', 'dark'] },
  ],
  limitations: ['Pebble fields produce many small candidates.'],
  score_definition: 'Dimensionless blob contrast. Not a probability.',
  experimental: false,
  produces_detections: true,
}
const texture: VisionMethod = {
  ...blob,
  name: 'texture',
  title: 'Texture classes (unsupervised)',
  category: 'segmentation',
  params: [],
  score_definition: null,
  experimental: true,
  produces_detections: false,
}

function analysis(method: string, extra: Partial<VisionAnalysis> = {}): VisionAnalysis {
  return {
    id: `${method}-id`,
    image_id: 'NLG_A',
    method,
    title: method,
    method_kind: 'algorithmic',
    provenance: 'derived',
    rendition: 'large',
    params: {},
    algorithm_version: '1',
    width: 1200,
    height: 900,
    timings_ms: { step: 12.5 },
    stats: method === 'rocks_blob' ? { candidates: 2 } : { class_1_share: 0.5 },
    detections: method === 'rocks_blob' ? [{ x: 10, y: 10, r: 5, score: 1.2, area_px: 78 }, { x: 50, y: 60, r: 8, score: 2, area_px: 200 }] : null,
    layers: method === 'texture' ? [{ name: 'texture', label: 'Texture classes', url: '/api/vision/analyses/t/layers/texture.png' }] : [],
    score_definition: method === 'rocks_blob' ? blob.score_definition : null,
    limitations: ['limit'],
    created_at: '2026-11-17T00:00:00Z',
    ...extra,
  }
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

function stub(handler: (url: URL, init?: RequestInit) => Response | undefined) {
  const posts: { url: string; body: unknown }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      if (init?.method === 'POST') posts.push({ url: url.pathname, body: init.body ? JSON.parse(String(init.body)) : null })
      return handler(url, init) ?? json({ error: { code: 'not_found', message: url.pathname } }, 404)
    }),
  )
  return posts
}

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/perception" element={<Perception />} />
        <Route path="/perception/:imageId" element={<Perception />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('Perception workspace', () => {
  function workspaceRoutes(url: URL, init?: RequestInit): Response | undefined {
    if (url.pathname === '/api/images/NLG_A') return json({ ...image, title: 'T', notes: [], source: {}, local_files: {} })
    if (url.pathname === '/api/vision/methods') return json([blob, texture])
    if (url.pathname === '/api/images/NLG_A/related') return json({ same_sequence: [], stereo: null, same_sol_other_cameras: [] })
    if (url.pathname === '/api/images/NLG_A/annotations') return json([])
    if (url.pathname === '/api/vision/analyses' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body)) as { method: string }
      return json(analysis(body.method))
    }
    return undefined
  }

  it('runs the default detector, labels the result honestly and switches methods', async () => {
    const posts = stub(workspaceRoutes)
    const user = userEvent.setup()
    renderAt('/perception/NLG_A')

    expect(await screen.findByText('Algorithmic · not a model prediction')).toBeInTheDocument()
    expect(screen.getByText('Dimensionless blob contrast. Not a probability.')).toBeInTheDocument()
    expect(screen.getByText('Candidates (2)')).toBeInTheDocument()
    expect(posts[0]).toEqual({ url: '/api/vision/analyses', body: { image_id: 'NLG_A', method: 'rocks_blob', params: {}, rendition: 'large' } })

    await user.click(screen.getByRole('button', { name: /Texture classes/ }))
    expect(await screen.findByText('Experimental method — read the limitations before drawing conclusions.')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Texture classes' })).toBeChecked()
    expect(screen.getByRole('tab', { name: 'Stereo match' })).toBeDisabled()
  })

  it('sends only changed parameters', async () => {
    const posts = stub(workspaceRoutes)
    const user = userEvent.setup()
    renderAt('/perception/NLG_A')
    await screen.findByText('Candidates (2)')
    await user.click(screen.getByRole('radio', { name: 'dark' }))
    await user.click(screen.getByRole('button', { name: 'Run' }))
    await waitFor(() => expect(posts).toHaveLength(2))
    expect(posts[1]!.body).toMatchObject({ params: { polarity: 'dark' } })
  })
})

describe('ParamForm', () => {
  it('clamps slider input and resets to defaults', () => {
    const onChange = vi.fn()
    const onReset = vi.fn()
    render(<ParamForm method={blob} values={{ min_radius: 10, polarity: 'both' }} onChange={onChange} onReset={onReset} />)
    fireEvent.change(screen.getByLabelText(/Min radius/), { target: { value: '12' } })
    expect(onChange).toHaveBeenCalledWith({ min_radius: 12, polarity: 'both' })
    fireEvent.click(screen.getByRole('button', { name: 'Reset to defaults' }))
    expect(onReset).toHaveBeenCalled()
  })
})

describe('EvaluationPanel', () => {
  const evaluation: Evaluation = {
    analysis_id: 'a',
    annotations: 4,
    detections: 5,
    true_positives: 3,
    false_positives: 2,
    false_negatives: 1,
    precision: 0.6,
    recall: 0.75,
    f1: 0.667,
    tolerance_px: 18,
    matching: 'greedy',
    caveats: ['assumes complete marking'],
  }
  const annotations = [1, 2, 3, 4].map((id) => ({
    id, image_id: 'NLG_A', x: 0.1, y: 0.1, label: 'rock', provenance: 'user_generated' as const, created_at: '',
  }))

  it('shows precision/recall and requires confirmation before clearing', async () => {
    const onClear = vi.fn()
    const user = userEvent.setup()
    render(
      <EvaluationPanel
        annotations={annotations}
        annotating={false}
        onToggleAnnotating={vi.fn()}
        onUndo={vi.fn()}
        onClear={onClear}
        evaluation={evaluation}
        evaluating={false}
        busy={false}
      />,
    )
    const metrics = screen.getByLabelText('Evaluation against your annotations')
    expect(within(metrics).getByText('60 %')).toBeInTheDocument()
    expect(within(metrics).getByText('75 %')).toBeInTheDocument()
    expect(screen.getByText('USER')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Clear all' }))
    expect(onClear).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Confirm: delete 4' }))
    expect(onClear).toHaveBeenCalledOnce()
  })
})

describe('Perception home', () => {
  it('runs the benchmark and shows per-detector results', async () => {
    stub((url, init) => {
      if (url.pathname === '/api/images') return json({ items: [image], total: 1, limit: 60, offset: 0 })
      if (url.pathname === '/api/vision/benchmark' && init?.method === 'POST')
        return json({
          images: 40,
          cameras: [],
          methods: [
            { method: 'rocks_blob', title: 'Rock candidates — scale-space blobs', images: 40, runtime_ms: { mean: 150, median: 152.3, p95: 164 }, candidates: { mean: 180, median: 186, p95: 290 }, annotated_images: 0, true_positives: 0, false_positives: 0, false_negatives: 0, precision: null, recall: null, f1: null },
          ],
          agreement_f1: { mean: 0.4, median: 0.37, p95: 0.6 },
          notes: ['Agreement is not accuracy.'],
        })
      return undefined
    })
    const user = userEvent.setup()
    renderAt('/perception')
    await screen.findByRole('region', { name: 'Sol 2022' })
    await user.click(screen.getByRole('button', { name: 'Run benchmark' }))
    const row = await screen.findByRole('row', { name: /scale-space blobs/ })
    expect(within(row).getByText('152.3')).toBeInTheDocument()
    expect(screen.getByText(/agreement between detectors \(F1 median\): 0.37/)).toBeInTheDocument()
  })
})
