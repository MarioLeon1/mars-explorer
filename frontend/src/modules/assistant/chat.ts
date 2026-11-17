/** Pure helpers for the assistant chat (tested in chat.test.ts). */

export type Segment = { kind: 'text'; text: string } | { kind: 'link'; text: string; to: string }

/** In-app paths the assistant is told to cite: /explorer/<id>, /perception/<id>, /replay?sol=N, /terrain. */
const APP_LINK = /(\/(?:explorer|perception)\/[A-Za-z0-9_]+|\/replay\?sol=\d+|\/terrain\b)/g

/** Split a reply into text and in-app link segments (only known app routes become links). */
export function linkify(text: string): Segment[] {
  const out: Segment[] = []
  let last = 0
  for (const match of text.matchAll(APP_LINK)) {
    const start = match.index
    if (start > last) out.push({ kind: 'text', text: text.slice(last, start) })
    out.push({ kind: 'link', text: match[0], to: match[0] })
    last = start + match[0].length
  }
  if (last < text.length) out.push({ kind: 'text', text: text.slice(last) })
  return out
}

/** Rough cost of one exchange in USD from token usage and per-million prices. */
export function estimateCostUsd(
  usage: { input_tokens: number; output_tokens: number; cache_read_input_tokens: number; cache_creation_input_tokens: number },
  price: { input_usd_per_mtok: number; output_usd_per_mtok: number } | undefined,
): number | null {
  if (!price) return null
  const input =
    usage.input_tokens + usage.cache_creation_input_tokens * 1.25 + usage.cache_read_input_tokens * 0.1
  return (input * price.input_usd_per_mtok + usage.output_tokens * price.output_usd_per_mtok) / 1_000_000
}

export const PRESETS = [
  'Give me an overview of the mission data stored in this app.',
  'Where is the rover now, and how far has it driven in total?',
  'Write a short mission report for the sol I am looking at.',
  'Which reconstructed sequences show real change over time, and which are pans?',
]
