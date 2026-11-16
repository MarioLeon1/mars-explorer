import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, imagesPath, request } from './client'

function mockFetch(impl: () => Promise<Response>) {
  vi.stubGlobal('fetch', vi.fn(impl))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('request', () => {
  it('returns parsed JSON on success', async () => {
    mockFetch(async () => new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))
    await expect(request('/api/health')).resolves.toEqual({ status: 'ok' })
  })

  it('maps the API error contract to ApiError', async () => {
    mockFetch(
      async () =>
        new Response(JSON.stringify({ error: { code: 'image_not_found', message: 'nope' } }), {
          status: 404,
        }),
    )
    const error = await request('/api/images/x').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, code: 'image_not_found', message: 'nope' })
    expect((error as ApiError).isUnreachable).toBe(false)
  })

  it('treats network failures as an unreachable backend', async () => {
    mockFetch(async () => {
      throw new TypeError('Failed to fetch')
    })
    const error = (await request('/api/health').catch((e: unknown) => e)) as ApiError
    expect(error.isUnreachable).toBe(true)
  })

  it('treats a non-JSON proxy 5xx as an unreachable backend', async () => {
    mockFetch(async () => new Response('', { status: 502 }))
    const error = (await request('/api/health').catch((e: unknown) => e)) as ApiError
    expect(error.code).toBe('backend_unreachable')
    expect(error.isUnreachable).toBe(true)
  })
})

describe('imagesPath', () => {
  it('encodes filters with repeatable cameras', () => {
    expect(imagesPath()).toBe('/api/images')
    expect(imagesPath({ sol: 2022, cameras: ['NAVCAM_LEFT', 'MCZ_LEFT'], limit: 40 })).toBe(
      '/api/images?sol=2022&camera=NAVCAM_LEFT&camera=MCZ_LEFT&limit=40',
    )
  })
})
