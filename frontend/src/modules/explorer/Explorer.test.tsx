import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ImageSummary } from '../../api/types'
import { SystemStatusProvider } from '../../app/SystemStatusContext'
import { Explorer } from './Explorer'

function summary(id: string, sol: number, instrument = 'NAVCAM_LEFT'): ImageSummary {
  return {
    image_id: id,
    sol,
    camera: { instrument, group: 'navcam', label: `${instrument} label` },
    sample_type: 'Full',
    date_taken_utc: '2026-10-28T11:17:45Z',
    date_taken_mars: null,
    lmst: '16:20:47',
    site: 93,
    drive: 0,
    width: 1280,
    height: 960,
    thumb_url: `/api/images/${id}/file/small`,
    preview_url: `/api/images/${id}/file/large`,
    credit: 'NASA/JPL-Caltech',
    provenance: 'real_observation',
  }
}

function detail(image: ImageSummary) {
  return {
    ...image,
    title: `Title ${image.image_id}`,
    caption: null,
    date_received: null,
    filter_name: null,
    sequence_id: 'NCAM00001',
    mast_az: 10,
    mast_el: -5,
    sclk: 1,
    scale_factor: 1,
    subframe_rect: null,
    attitude_quaternion: null,
    camera_model_type: 'CAHVORE',
    camera_position: null,
    camera_vector: null,
    source: { nasa_page_url: 'https://mars.nasa.gov/x', nasa_json_url: null, original_files: { small: null, medium: null, large: null, full_res: null } },
    local_files: { small: true, large: true, full_res: false },
    ingested_at: '2026-11-16T00:00:00Z',
    notes: ['Uncalibrated browse product.'],
  }
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

type Handler = (url: URL, init?: RequestInit) => Response | undefined

function stubApi(handler: Handler) {
  const calls: { url: URL; method: string }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      calls.push({ url, method: init?.method ?? 'GET' })
      const fallback: Record<string, unknown> = {
        '/api/cameras': [
          { instrument: 'NAVCAM_LEFT', group: 'navcam', label: 'Navcam left', image_count: 3 },
          { instrument: 'MCZ_LEFT', group: 'mastcamz', label: 'Mastcam-Z left', image_count: 0 },
        ],
        '/api/sols': [{ sol: 2022, image_count: 2, instruments: ['NAVCAM_LEFT'], earliest_utc: null, latest_utc: null }],
        '/api/system/status': {
          api: 'ok',
          database: { images: 3, sols: 2, waypoints: 0 },
          storage: { image_files: 6, bytes: 1000 },
          last_ingest: null,
          feed: { latest_sol: 2031, total_images: 1, checked_at: '2026-11-16T00:00:00Z' },
        },
        '/api/ingest/jobs': [],
      }
      const response = handler(url, init)
      if (response) return response
      if (url.pathname in fallback) return json(fallback[url.pathname])
      return json({ error: { code: 'not_found', message: `no stub for ${url.pathname}` } }, 404)
    }),
  )
  return calls
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname + location.search}</output>
}

function renderExplorer(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <SystemStatusProvider>
        <Routes>
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/explorer/:imageId" element={<Explorer />} />
        </Routes>
        <LocationProbe />
      </SystemStatusProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

const A = summary('NLG_A', 2022)
const B = summary('NLG_B', 2022)
const C = summary('NLG_C', 1503)

describe('Explorer grid', () => {
  it('applies URL filters to the API and groups results by sol', async () => {
    const calls = stubApi((url) =>
      url.pathname === '/api/images' ? json({ items: [A, B, C], total: 3, limit: 60, offset: 0 }) : undefined,
    )
    renderExplorer('/explorer?camera=NAVCAM_LEFT&sol_min=1000')
    expect(await screen.findByRole('region', { name: 'Sol 2022' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Sol 1503' })).toBeInTheDocument()
    const listCall = calls.find((c) => c.url.pathname === '/api/images')!
    expect(listCall.url.searchParams.getAll('camera')).toEqual(['NAVCAM_LEFT'])
    expect(listCall.url.searchParams.get('sol_min')).toBe('1000')
    expect(screen.getByText(/3 of 3 · sols 1000–… · NAVCAM_LEFT/)).toBeInTheDocument()
  })

  it('updates the URL when a camera filter is toggled', async () => {
    stubApi((url) => (url.pathname === '/api/images' ? json({ items: [A], total: 1, limit: 60, offset: 0 }) : undefined))
    const user = userEvent.setup()
    renderExplorer('/explorer')
    await user.click(await screen.findByRole('checkbox', { name: /NAVCAM LEFT/ }))
    expect(screen.getByTestId('location')).toHaveTextContent('/explorer?camera=NAVCAM_LEFT')
  })

  it('explains an empty result and offers to clear filters', async () => {
    stubApi((url) => (url.pathname === '/api/images' ? json({ items: [], total: 0, limit: 60, offset: 0 }) : undefined))
    const user = userEvent.setup()
    renderExplorer('/explorer?sol=5')
    expect(await screen.findByText('No stored images match these filters')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Clear filters' }))
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/explorer$/)
  })

  it('opens the detail view keeping the filters in the URL', async () => {
    stubApi((url) => {
      if (url.pathname === '/api/images') return json({ items: [A, B], total: 2, limit: 60, offset: 0 })
      if (url.pathname === '/api/images/NLG_B') return json(detail(B))
      return undefined
    })
    const user = userEvent.setup()
    renderExplorer('/explorer?sol=2022')
    const card = await screen.findByTitle(/NLG_B/)
    await user.click(card)
    expect(screen.getByTestId('location')).toHaveTextContent('/explorer/NLG_B?sol=2022')
  })
})

describe('Explorer detail', () => {
  function detailRoutes(extra?: Handler): Handler {
    return (url, init) => {
      const custom = extra?.(url, init)
      if (custom) return custom
      if (url.pathname === '/api/images/NLG_B') return json(detail(B))
      if (url.pathname === '/api/images/NLG_B/neighbors') return json({ previous: A, next: C, position: 2, total: 3 })
      if (url.pathname === '/api/images/NLG_B/related')
        return json({
          same_sequence: [A],
          stereo: { partner_instrument: 'NAVCAM_RIGHT', candidate_id: 'NRG_B', local: null },
          same_sol_other_cameras: [],
        })
      return undefined
    }
  }

  it('shows metadata, position and chronological navigation', async () => {
    const calls = stubApi(detailRoutes())
    const user = userEvent.setup()
    renderExplorer('/explorer/NLG_B?camera=NAVCAM_LEFT')
    expect(await screen.findByText('Title NLG_B')).toBeInTheDocument()
    expect(await screen.findByText('2 / 3')).toBeInTheDocument()
    expect(calls.find((c) => c.url.pathname.endsWith('/neighbors'))!.url.searchParams.get('camera')).toBe('NAVCAM_LEFT')
    await user.click(screen.getByRole('button', { name: /Later/ }))
    expect(screen.getByTestId('location')).toHaveTextContent('/explorer/NLG_C?camera=NAVCAM_LEFT')
  })

  it('reports honestly when NASA has not published the stereo partner', async () => {
    stubApi(
      detailRoutes((url, init) =>
        url.pathname === '/api/images/NLG_B/stereo-partner' && init?.method === 'POST'
          ? json({ error: { code: 'stereo_partner_not_found', message: 'not published' } }, 404)
          : undefined,
      ),
    )
    const user = userEvent.setup()
    renderExplorer('/explorer/NLG_B')
    const stereo = await screen.findByRole('region', { name: 'Stereo pair' })
    await user.click(within(stereo).getByRole('button', { name: 'Fetch from NASA' }))
    expect(await within(stereo).findByText(/NASA has not published a matching frame/)).toBeInTheDocument()
    expect(within(stereo).getByRole('button', { name: 'Fetch from NASA' })).toBeDisabled()
  })

  it('fetches a published stereo partner and offers the comparison', async () => {
    let fetched = false
    const right = summary('NRG_B', 2022, 'NAVCAM_RIGHT')
    stubApi(
      detailRoutes((url, init) => {
        if (url.pathname === '/api/images/NLG_B/stereo-partner' && init?.method === 'POST') {
          fetched = true
          return json(right)
        }
        if (url.pathname === '/api/images/NLG_B/related' && fetched)
          return json({
            same_sequence: [],
            stereo: { partner_instrument: 'NAVCAM_RIGHT', candidate_id: 'NRG_B', local: right },
            same_sol_other_cameras: [],
          })
        return undefined
      }),
    )
    const user = userEvent.setup()
    renderExplorer('/explorer/NLG_B')
    const stereo = await screen.findByRole('region', { name: 'Stereo pair' })
    await user.click(within(stereo).getByRole('button', { name: 'Fetch from NASA' }))
    expect(await within(stereo).findByText('STEREO')).toBeInTheDocument()
    await user.click(within(stereo).getByRole('button', { name: 'Compare' }))
    expect(screen.getByText(/Real stereo pair, captured together/)).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'Swipe' }))
    expect(screen.getByRole('slider', { name: /Swipe position/ })).toHaveAttribute('aria-valuenow', '50')
  })
})

describe('Add data from NASA', () => {
  it('checks availability, starts a job and reloads the archive when it finishes', async () => {
    let jobDone = false
    let imagesCalls = 0
    const job = {
      id: 'job1',
      status: 'queued',
      sol_min: 1201,
      sol_max: 1201,
      cameras: ['NAVCAM_LEFT', 'NAVCAM_RIGHT'],
      limit: 40,
      full_res: false,
      progress: { seen: 0, added: 0, skipped: 0, failed: 0, downloaded: 0 },
      run_id: null,
      error: null,
      created_at: '2026-11-16T00:00:00Z',
      started_at: null,
      finished_at: null,
    }
    stubApi((url, init) => {
      if (url.pathname === '/api/images') {
        imagesCalls += 1
        return json({ items: [A], total: 1, limit: 60, offset: 0 })
      }
      if (url.pathname === '/api/feed/availability')
        return json({ sol_min: 1201, sol_max: 1201, cameras: [], published: 32, stored: 0, checked_at: '2026-11-16T00:00:00Z', source: { name: 'feed', url: 'https://x', credit: null, retrieved_at: null } })
      if (url.pathname === '/api/ingest/jobs' && init?.method === 'POST') return json(job, 202)
      if (url.pathname === '/api/ingest/jobs') {
        const current = jobDone
          ? { ...job, status: 'success', progress: { seen: 32, added: 32, skipped: 0, failed: 0, downloaded: 64 } }
          : { ...job, status: 'running' }
        jobDone = true
        return json([current])
      }
      return undefined
    })
    const user = userEvent.setup()
    renderExplorer('/explorer')
    await screen.findByRole('region', { name: 'Sol 2022' })
    await user.click(screen.getByRole('button', { name: /Add data from NASA/ }))
    await user.type(screen.getByLabelText('Sol'), '1201')
    await user.click(screen.getByRole('button', { name: 'Check NASA' }))
    expect(await screen.findByText(/NASA publishes 32 · 0 stored/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Download' }))
    expect(await screen.findByText('success', {}, { timeout: 4000 })).toBeInTheDocument()
    await waitFor(() => expect(imagesCalls).toBeGreaterThanOrEqual(2))
  })
})
