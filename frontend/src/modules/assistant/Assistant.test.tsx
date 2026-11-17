import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AssistantStatus, ChatResponse } from '../../api/types'
import { Assistant } from './Assistant'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const status: AssistantStatus = {
  enabled: false,
  model: 'claude-opus-5-5',
  effort: 'medium',
  fallbacks: true,
  max_tool_rounds: 8,
  tools: [{ name: 'get_rover_position', description: 'Latest real localization.' }],
  how_to_enable: ['Create an API key', 'Add ANTHROPIC_API_KEY=<your key> to .env', 'Restart the backend'],
  data_sent: ['Your questions.'],
  never: ['The assistant cannot plan routes.'],
  pricing: [{ model: 'claude-opus-5-5', input_usd_per_mtok: 4, output_usd_per_mtok: 20, note: 'Default' }],
}

const reply: ChatResponse = {
  reply: 'The latest localization is from sol 2024. See /replay?sol=2024.',
  model: 'claude-opus-5-5',
  stop_reason: 'end_turn',
  refused: false,
  fallback_used: false,
  rounds: 2,
  tool_calls: [{ name: 'get_rover_position', input: {}, is_error: false, result_chars: 300 }],
  usage: { input_tokens: 2000, output_tokens: 100, cache_read_input_tokens: 0, cache_creation_input_tokens: 0 },
  notes: [],
  label: 'ai_generated',
  provenance: 'derived',
}

afterEach(() => vi.unstubAllGlobals())

describe('Assistant', () => {
  it('without a key explains how to enable it, the data sent and the cost', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(status)))
    render(
      <MemoryRouter>
        <Assistant />
      </MemoryRouter>,
    )
    expect(await screen.findByText('AI assistant · not configured')).toBeInTheDocument()
    expect(screen.getByText('Add ANTHROPIC_API_KEY=<your key> to .env')).toBeInTheDocument()
    expect(screen.getByText('ANTHROPIC_API_KEY=sk-ant-...')).toBeInTheDocument()
    expect(screen.getByText('The assistant cannot plan routes.')).toBeInTheDocument()
    expect(screen.getByText('$4.00')).toBeInTheDocument()
    expect(screen.queryByRole('textbox', { name: 'Message' })).not.toBeInTheDocument()
  })

  it('with a key sends the conversation with context and shows an AI-labelled answer', async () => {
    const bodies: unknown[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input).endsWith('/api/assistant/chat')) {
          bodies.push(JSON.parse(String(init?.body)))
          return json(reply)
        }
        return json({ ...status, enabled: true })
      }),
    )
    render(
      <MemoryRouter initialEntries={['/assistant?sol=2024']}>
        <Assistant />
      </MemoryRouter>,
    )
    await userEvent.type(await screen.findByRole('textbox', { name: 'Message' }), 'Where is the rover?{Enter}')
    expect(await screen.findByText('AI-GENERATED')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '/replay?sol=2024' })).toHaveAttribute('href', '/replay?sol=2024')
    expect(screen.getByText(/1 tool call\(s\)/)).toHaveTextContent('≈ $0.0100')
    await waitFor(() =>
      expect(bodies).toEqual([
        { messages: [{ role: 'user', content: 'Where is the rover?' }], context: { page: 'assistant', sol: 2024 } },
      ]),
    )
  })

  it('shows API errors in the conversation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).endsWith('/chat')
          ? json({ error: { code: 'assistant_auth_failed', message: 'The Anthropic API rejected the API key (401).' } }, 502)
          : json({ ...status, enabled: true }),
      ),
    )
    render(
      <MemoryRouter>
        <Assistant />
      </MemoryRouter>,
    )
    await userEvent.click(await screen.findByRole('button', { name: /overview of the mission/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('rejected the API key')
  })
})
