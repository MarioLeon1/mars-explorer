import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { FeaturedSequence, MissionTimeline, OfficialVideo, SequenceDetail, SolTimeline } from '../../api/types'
import { Replay } from './Replay'
import { SequencePlayer } from './SequencePlayer'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const camera = { instrument: 'NAVCAM_LEFT', group: 'navcam' as const, label: 'Navigation Camera — left (Navcam)' }

const mission: MissionTimeline = {
  sols: [
    { sol: 1000, images: 0, sequences: 0, drives: 2, drive_m: 40 },
    { sol: 2024, images: 4, sequences: 1, drives: 0, drive_m: 0 },
  ],
  total_drive_m: 40,
  drive_sols: 1,
  image_sols: 1,
  provenance: 'real_observation',
  sources: [],
  notes: [],
}

const summary = {
  id: '2024-NAVCAM_LEFT-NCAM00520',
  sol: 2024,
  camera,
  sequence_id: 'NCAM00520',
  kind: 'fixed_pointing' as const,
  kind_note: 'The camera kept the same pointing.',
  frame_count: 3,
  duration_s: 50,
  median_interval_s: 25,
  distinct_pointings: 1,
  start_lmst: '14:00:00',
  thumb_url: '/api/images/A/file/small',
  label: 'reconstructed' as const,
  provenance: 'derived' as const,
}

const frames = ['A', 'B', 'C'].map((id, i) => ({
  image_id: id,
  t_offset_s: i * 25,
  sclk: 1000 + i * 25,
  lmst: `14:00:${String(i * 25).padStart(2, '0')}`,
  width: 1280,
  height: 960,
  thumb_url: `/api/images/${id}/file/small`,
  preview_url: `/api/images/${id}/file/large`,
  provenance: 'real_observation' as const,
}))

const detail: SequenceDetail = {
  ...summary,
  frames,
  notes: ['Reconstructed from individual raw images in spacecraft-clock order. This is not a NASA video.'],
  credits: ['NASA/JPL-Caltech'],
  real_time_available: true,
}

const timeline: SolTimeline = {
  sol: 2024,
  images: frames.map((f, i) => ({
    image_id: f.image_id,
    camera,
    lmst: f.lmst,
    lmst_h: 14 + i / 144,
    sclk: f.sclk,
    sequence_id: 'NCAM00520',
    thumb_url: f.thumb_url,
  })),
  sequences: [summary],
  drives: [],
  end_of_sol_position: null,
  lmst_calibration: { samples: 3, max_residual_s: 0.5, method: 'linear' },
  previous_sol: 1000,
  next_sol: null,
  notes: [],
}

const featured: FeaturedSequence[] = [
  {
    key: 'landing-lcam',
    title: 'Landing day: Lander Vision System camera',
    description: '87 frames during descent.',
    sol: 0,
    camera: { instrument: 'LCAM', group: 'edl', label: 'Lander Vision System Camera (LCAM)' },
    sequence_id: 'LVS',
    published_frames: 87,
    local_frames: 0,
    sequence_url: null,
    job_request: { sol_min: 0, sol_max: 0, cameras: ['LCAM'], limit: 100, full_res: false },
    provenance: 'real_observation',
  },
]

const videos: OfficialVideo[] = [
  {
    nasa_id: 'JPL-landing',
    title: "Perseverance Rover's Descent and Touchdown on Mars",
    date: '2021-02-22',
    sol: 0,
    description: 'Real footage.',
    credit: 'NASA/JPL-Caltech',
    video_url: 'https://images-assets.nasa.gov/video/x~medium.mp4',
    poster_url: 'https://images-assets.nasa.gov/video/x~small.jpg',
    page_url: 'https://images.nasa.gov/details/x',
    label: 'official_nasa_video',
    provenance: 'real_observation',
  },
]

function stubApi(posted: unknown[] = []) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), 'http://localhost')
      if (init?.method === 'POST') {
        posted.push(JSON.parse(String(init.body)))
        return json({ id: 'job1', status: 'queued', progress: { seen: 0, added: 0, skipped: 0, failed: 0, downloaded: 0 } }, 202)
      }
      switch (url.pathname) {
        case '/api/replay/mission':
          return json(mission)
        case '/api/replay/featured':
          return json(featured)
        case '/api/replay/videos':
          return json(videos)
        case '/api/replay/sols/2024':
          return json(timeline)
        case `/api/replay/sequences/${summary.id}`:
          return json(detail)
        case '/api/ingest/jobs':
          return json([])
        default:
          return json({ error: { code: 'not_found', message: 'nope' } }, 404)
      }
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('Replay', () => {
  it('opens the latest sol with images and plays its time series, labelled as reconstructed', async () => {
    stubApi()
    render(
      <MemoryRouter initialEntries={['/replay']}>
        <Replay />
      </MemoryRouter>,
    )
    expect(await screen.findByText('Sol 2024 timeline')).toBeInTheDocument()
    expect(await screen.findByText('RECONSTRUCTED · not a NASA video')).toBeInTheDocument()
    expect(screen.getByText('Fixed pointing')).toBeInTheDocument()
    expect(screen.getByText(/This is not a NASA video/)).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /NAVCAM_LEFT image at LMST/ })).toHaveLength(3)
  })

  it('plays an official NASA video with its own label and credit', async () => {
    stubApi()
    render(
      <MemoryRouter initialEntries={['/replay?sol=2024&video=JPL-landing']}>
        <Replay />
      </MemoryRouter>,
    )
    expect(await screen.findByText('OFFICIAL NASA VIDEO')).toBeInTheDocument()
    expect(screen.queryByText('RECONSTRUCTED · not a NASA video')).not.toBeInTheDocument()
    expect(document.querySelector('video')?.getAttribute('src')).toBe(videos[0]?.video_url)
  })

  it('downloads a featured sequence through the ingest job API', async () => {
    const posted: unknown[] = []
    stubApi(posted)
    render(
      <MemoryRouter initialEntries={['/replay']}>
        <Replay />
      </MemoryRouter>,
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Download 87 frames from NASA' }))
    await waitFor(() => expect(posted).toEqual([featured[0]?.job_request]))
    expect(await screen.findByRole('button', { name: 'Downloading…' })).toBeDisabled()
  })
})

describe('SequencePlayer', () => {
  it('advances with the real gap divided by the speed', () => {
    vi.useFakeTimers()
    render(
      <MemoryRouter>
        <SequencePlayer sequence={detail} />
      </MemoryRouter>,
    )
    expect(screen.getByText('1/3 · +0.0 s')).toBeInTheDocument()
    act(() => screen.getByRole('button', { name: 'Play' }).click())
    // 25 s real gap at the default 10x = 2.5 s.
    act(() => vi.advanceTimersByTime(2400))
    expect(screen.getByText('1/3 · +0.0 s')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(200))
    expect(screen.getByText('2/3 · +25.0 s')).toBeInTheDocument()
    expect(screen.getByText(/later/)).toHaveTextContent('next exposure 25.0 s later')
  })
})
