import { describe, expect, it } from 'vitest'
import { estimateCostUsd, linkify } from './chat'

describe('linkify', () => {
  it('turns known app routes into links and keeps the rest as text', () => {
    expect(linkify('See /explorer/NLF_2022_X1 and /replay?sol=2022.')).toEqual([
      { kind: 'text', text: 'See ' },
      { kind: 'link', text: '/explorer/NLF_2022_X1', to: '/explorer/NLF_2022_X1' },
      { kind: 'text', text: ' and ' },
      { kind: 'link', text: '/replay?sol=2022', to: '/replay?sol=2022' },
      { kind: 'text', text: '.' },
    ])
  })

  it('leaves external URLs and unknown paths alone', () => {
    expect(linkify('https://mars.nasa.gov/ and /admin')).toEqual([{ kind: 'text', text: 'https://mars.nasa.gov/ and /admin' }])
    expect(linkify('')).toEqual([])
  })
})

describe('estimateCostUsd', () => {
  it('prices cache reads at 10 % and cache writes at 125 %', () => {
    const usage = { input_tokens: 1_000_000, output_tokens: 100_000, cache_read_input_tokens: 1_000_000, cache_creation_input_tokens: 0 }
    expect(estimateCostUsd(usage, { input_usd_per_mtok: 4, output_usd_per_mtok: 20 })).toBeCloseTo(4 + 0.4 + 2)
    expect(estimateCostUsd(usage, undefined)).toBeNull()
  })
})
