/**
 * upstream/copilot-bridge.ts
 *
 * Streams a chat completion from a GitHub-Copilot-compatible SSE endpoint.
 * In Phase B we only need the contract — `MOCK_UPSTREAM=1` short-circuits to
 * a deterministic in-memory generator so vitest never touches the network
 * (and so dev without a token still demos correctly).
 */

import type { ChatMessage } from '@oc/shared/chat'

export interface StreamCopilotArgs {
  messages: ChatMessage[] | Array<{ role: string; content: string }>
  model?: string
  signal?: AbortSignal
  onDelta: (delta: string) => void
  onComplete: (output: string) => void
  onError: (err: Error) => void
}

const UPSTREAM_URL =
  process.env.OPENCLAW_COPILOT_URL ||
  'https://api.githubcopilot.com/chat/completions'

export async function streamCopilot(args: StreamCopilotArgs): Promise<void> {
  if (process.env.MOCK_UPSTREAM === '1') {
    return runMock(args)
  }
  return runReal(args)
}

// ---------- mock generator ----------

function runMock(args: StreamCopilotArgs): Promise<void> {
  return new Promise((resolve) => {
    let i = 0
    const total = 10
    const collected: string[] = []

    const tick = () => {
      if (args.signal?.aborted) {
        args.onError(new Error('aborted'))
        return resolve()
      }
      if (i >= total) {
        args.onComplete('done')
        return resolve()
      }
      const delta = `token-${i}`
      collected.push(delta)
      args.onDelta(delta)
      i += 1
      timer = setTimeout(tick, 100)
    }

    let timer: NodeJS.Timeout = setTimeout(tick, 0)

    args.signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      args.onError(new Error('aborted'))
      resolve()
    })
  })
}

// ---------- real SSE ----------

async function runReal(args: StreamCopilotArgs): Promise<void> {
  try {
    const token = process.env.OPENCLAW_COPILOT_TOKEN
    const headers: Record<string, string> = {
      'content-type': 'application/json',
      accept: 'text/event-stream',
    }
    if (token) headers.authorization = `Bearer ${token}`

    const res = await fetch(UPSTREAM_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        model: args.model || 'gpt-4o-mini',
        messages: args.messages,
        stream: true,
      }),
      signal: args.signal,
    })

    if (!res.ok || !res.body) {
      args.onError(new Error(`upstream ${res.status} ${res.statusText}`))
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buf = ''
    let collected = ''

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })

      let nl: number
      while ((nl = buf.indexOf('\n')) !== -1) {
        const line = buf.slice(0, nl).trimEnd()
        buf = buf.slice(nl + 1)
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (payload === '[DONE]') {
          args.onComplete(collected)
          return
        }
        try {
          const obj = JSON.parse(payload)
          const delta: string | undefined = obj?.choices?.[0]?.delta?.content
          if (typeof delta === 'string' && delta.length > 0) {
            collected += delta
            args.onDelta(delta)
          }
        } catch {
          /* ignore malformed frames */
        }
      }
    }

    args.onComplete(collected)
  } catch (err: any) {
    if (err?.name === 'AbortError') {
      args.onError(new Error('aborted'))
    } else {
      args.onError(err instanceof Error ? err : new Error(String(err)))
    }
  }
}
