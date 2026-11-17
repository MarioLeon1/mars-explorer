import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../../api/client'
import type { AssistantStatus, ChatContext, ChatMessage, ChatResponse } from '../../api/types'
import { useApi } from '../../api/useApi'
import { Panel } from '../../design-system/Panel'
import { ProvenanceBadge } from '../../design-system/ProvenanceBadge'
import { CommandHint, ErrorState, SkeletonBlock } from '../../design-system/primitives'
import { formatNumber } from '../../lib/format'
import './assistant.css'
import { estimateCostUsd, linkify, PRESETS } from './chat'

interface Turn {
  message: ChatMessage
  response?: ChatResponse
  error?: string
}

function Reply({ text }: { text: string }) {
  return (
    <p className="as-text">
      {linkify(text).map((segment, i) =>
        segment.kind === 'link' ? (
          <Link key={i} to={segment.to} className="mono">
            {segment.text}
          </Link>
        ) : (
          <span key={i}>{segment.text}</span>
        ),
      )}
    </p>
  )
}

function SetupGuide({ status }: { status: AssistantStatus }) {
  return (
    <div className="as-setup">
      <Panel title="AI assistant · not configured">
        <p className="as-lead">
          The assistant is fully built but switched off: it needs your own Anthropic API key. Everything else in Mars
          Explorer works without it.
        </p>
        <ol className="as-steps">
          {status.how_to_enable.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
        <p>
          <a href="https://platform.claude.com/settings/keys" target="_blank" rel="noreferrer">
            Open the Claude Console (API keys) ↗
          </a>
        </p>
        <p className="as-muted">In the .env file (project root) the line looks like this:</p>
        <CommandHint command="ANTHROPIC_API_KEY=sk-ant-..." />
        <p className="as-muted">
          Model configured now: <span className="mono">{status.model}</span> (effort{' '}
          <span className="mono">{status.effort}</span>). Change it with <span className="mono">MARS_ASSISTANT_MODEL</span>.
        </p>
      </Panel>
      <div className="as-setup__grid">
        <Panel title="What is sent to Anthropic">
          <ul className="as-bullets">
            {status.data_sent.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="label as-sub">Never</p>
          <ul className="as-bullets">
            {status.never.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </Panel>
        <Panel title="Cost (pay per use, USD per million tokens)">
          <table className="as-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Input</th>
                <th>Output</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {status.pricing.map((p) => (
                <tr key={p.model} className={p.model === status.model ? 'is-current' : ''}>
                  <td className="mono">{p.model}</td>
                  <td className="mono">${formatNumber(p.input_usd_per_mtok, 2)}</td>
                  <td className="mono">${formatNumber(p.output_usd_per_mtok, 2)}</td>
                  <td>{p.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="as-muted">
            A typical question uses a few thousand tokens (a few cents with the default model). Each answer shows its
            token usage and estimated cost.
          </p>
        </Panel>
        <Panel title="Read-only tools it can use">
          <ul className="as-tools">
            {status.tools.map((tool) => (
              <li key={tool.name}>
                <span className="mono">{tool.name}</span>
                <span>{tool.description}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  )
}

export function Assistant() {
  const status = useApi('assistant-status', api.assistantStatus)
  const [params] = useSearchParams()
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [sol, setSol] = useState(params.get('sol') ?? '')
  const [imageId, setImageId] = useState(params.get('image') ?? '')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [turns.length, busy])

  if (status.state.status === 'loading') return <SkeletonBlock lines={6} />
  if (status.state.status === 'error')
    return <ErrorState title="Assistant status unavailable" message={status.state.error.message} onRetry={status.retry} />
  const info = status.state.data
  if (!info.enabled) return <SetupGuide status={info} />

  const price = info.pricing.find((p) => info.model.startsWith(p.model))

  const send = async (text: string) => {
    const content = text.trim()
    if (!content || busy) return
    const history: ChatMessage[] = [
      ...turns.flatMap((t) =>
        t.response && !t.response.refused
          ? [t.message, { role: 'assistant' as const, content: t.response.reply }]
          : [],
      ),
      { role: 'user', content },
    ]
    const context: ChatContext = { page: 'assistant' }
    if (/^\d+$/.test(sol)) context.sol = Number(sol)
    if (imageId.trim()) context.image_id = imageId.trim()
    setTurns((t) => [...t, { message: { role: 'user', content } }])
    setDraft('')
    setBusy(true)
    try {
      const response = await api.chat(history.slice(-40), context)
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, response } : turn)))
    } catch (error) {
      const message = error instanceof ApiError ? error.message : String(error)
      setTurns((t) => t.map((turn, i) => (i === t.length - 1 ? { ...turn, error: message } : turn)))
    } finally {
      setBusy(false)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void send(draft)
  }

  return (
    <div className="as">
      <Panel
        title="Mission assistant"
        className="as-chat"
        meta={
          <span className="as-muted">
            <span className="mono">{info.model}</span> · read-only tools · never controls the rover
          </span>
        }
      >
        <div className="as-log" aria-live="polite">
          {turns.length === 0 && (
            <div className="as-empty">
              <p className="as-lead">Ask about the stored mission data. Answers cite where facts come from.</p>
              <div className="as-presets">
                {PRESETS.map((preset) => (
                  <button key={preset} type="button" className="ds-button" onClick={() => void send(preset)}>
                    {preset}
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((turn, i) => (
            <div key={i} className="as-turn">
              <div className="as-msg as-msg--user">
                <span className="label">You</span>
                <p className="as-text">{turn.message.content}</p>
              </div>
              {turn.response && (
                <div className={`as-msg as-msg--ai ${turn.response.refused ? 'as-msg--refused' : ''}`}>
                  <span className="as-msg__head">
                    <span className="label">Assistant</span>
                    <ProvenanceBadge provenance={turn.response.provenance} />
                    <span className="as-ai">AI-GENERATED</span>
                  </span>
                  <Reply text={turn.response.reply} />
                  {turn.response.notes.map((note) => (
                    <p key={note} className="as-muted">
                      {note}
                    </p>
                  ))}
                  <details className="as-details">
                    <summary>
                      {turn.response.tool_calls.length} tool call(s) · {formatNumber(turn.response.usage.input_tokens)} in /{' '}
                      {formatNumber(turn.response.usage.output_tokens)} out tokens
                      {(() => {
                        const cost = estimateCostUsd(turn.response.usage, price)
                        return cost === null ? '' : ` · ≈ $${cost.toFixed(4)}`
                      })()}
                      {turn.response.fallback_used && ` · answered by fallback model ${turn.response.model}`}
                    </summary>
                    <ul>
                      {turn.response.tool_calls.map((call, k) => (
                        <li key={k} className="mono">
                          {call.name}({JSON.stringify(call.input)}){call.is_error ? ' → error' : ''}
                        </li>
                      ))}
                    </ul>
                  </details>
                </div>
              )}
              {turn.error && (
                <div className="as-msg as-msg--error" role="alert">
                  <span className="label">Error</span>
                  <p className="as-text">{turn.error}</p>
                </div>
              )}
            </div>
          ))}
          {busy && (
            <p className="as-muted" role="status">
              Thinking and looking things up…
            </p>
          )}
          <div ref={endRef} />
        </div>
        <form className="as-form" onSubmit={submit}>
          <div className="as-context">
            <span className="label">Context</span>
            <label>
              sol <input className="mono" value={sol} onChange={(e) => setSol(e.target.value)} size={6} inputMode="numeric" />
            </label>
            <label>
              image <input className="mono" value={imageId} onChange={(e) => setImageId(e.target.value)} size={28} />
            </label>
            {turns.length > 0 && (
              <button type="button" className="ds-button" onClick={() => setTurns([])} disabled={busy}>
                New conversation
              </button>
            )}
          </div>
          <div className="as-input">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void send(draft)
                }
              }}
              placeholder="Ask about images, sols, drives, sequences…"
              rows={2}
              maxLength={8000}
              aria-label="Message"
            />
            <button type="submit" className="ds-button" disabled={busy || !draft.trim()}>
              Send
            </button>
          </div>
        </form>
      </Panel>
    </div>
  )
}
