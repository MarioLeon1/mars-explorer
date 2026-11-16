import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ImageSummary } from '../../api/types'
import { SystemStatusProvider } from '../../app/SystemStatusContext'
import { MissionControl } from './MissionControl'

function summary(id: string, sol: number, instrument = 'NAVCAM_LEFT'): ImageSummary {
  return {
    image_id: id,
    sol,
    camera: { instrument, group: 'navcam', label: 'Navigation Camera — left (Navcam)' },
    sample_type: 'Full',
    date_taken_utc: '2026-10-28T11:17:45Z',
    date_taken_mars: 'Sol-02022M16:20:47.171',
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

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

/** Route-based fetch stub; unknown routes answer 404 with the API error contract. */
function stubApi(routes: Record<string, () => Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    const path = url.split('?')[0]!
    const handler = routes[url] ?? routes[path]
    return handler ? handler() : json({ error: { code: 'not_found', message: `no stub for ${url}` } }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderMc() {
  return render(
    <MemoryRouter>
      <SystemStatusProvider>
        <MissionControl />
      </SystemStatusProvider>
    </MemoryRouter>,
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('MissionControl', () => {
  it('shows the ingest command when the archive is empty', async () => {
    stubApi({ '/api/images': () => json({ items: [], total: 0, limit: 60, offset: 0 }) })
    renderMc()
    expect(await screen.findByText('No observations in the local archive yet')).toBeInTheDocument()
    expect(screen.getByText('cd backend; uv run mars-ingest seed')).toBeInTheDocument()
  })

  it('explains how to start the backend when it is unreachable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    renderMc()
    expect(await screen.findByText('The Mars Explorer API is not reachable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('selects observations from the filmstrip and with the arrow keys', async () => {
    const items = [summary('IMG_A', 2022), summary('IMG_B', 2022), summary('IMG_C', 1503)]
    stubApi({
      '/api/images': () => json({ items, total: 3, limit: 60, offset: 0 }),
      '/api/images/IMG_A': () => json({ ...items[0], title: 'Title A', notes: [], source: {}, local_files: {} }),
      '/api/images/IMG_B': () => json({ ...items[1], title: 'Title B', notes: [], source: {}, local_files: {} }),
      '/api/images/IMG_C': () => json({ ...items[2], title: 'Title C', notes: [], source: {}, local_files: {} }),
    })
    const user = userEvent.setup()
    renderMc()

    const strip = await screen.findByRole('region', { name: 'Recent observations' })
    expect(within(strip).getByRole('group', { name: 'Sol 2022' })).toBeInTheDocument()
    expect(within(strip).getByRole('group', { name: 'Sol 1503' })).toBeInTheDocument()

    // First item is selected by default.
    expect(await screen.findByText('Title A')).toBeInTheDocument()
    const thumbs = within(strip).getAllByRole('button')
    expect(thumbs[0]).toHaveAttribute('aria-pressed', 'true')

    await user.click(thumbs[2]!)
    expect(await screen.findByText('Title C')).toBeInTheDocument()
    expect(thumbs[2]).toHaveAttribute('aria-pressed', 'true')

    await user.keyboard('{ArrowLeft}')
    await waitFor(() => expect(thumbs[1]).toHaveAttribute('aria-pressed', 'true'))
    expect(await screen.findByText('Title B')).toBeInTheDocument()
  })
})
