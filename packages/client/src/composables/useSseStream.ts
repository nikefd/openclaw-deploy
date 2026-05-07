/**
 * useSseStream — pure SSE client for `/v2/api/copilot/stream`.
 *
 * Phase E2b: replaces the socket.io fixture path with a real fetch+SSE
 * implementation modeled after legacy /var/www/chat/index.html `send()`.
 *
 * Frame format (OpenAI-style chat/completions stream):
 *   data: {"choices":[{"delta":{"content":"..."}}]}\n\n
 *   ...
 *   data: [DONE]\n\n
 *
 * We only need `choices[0].delta.content`. Any other shape is tolerated
 * (parse errors silently ignored, matching the legacy parser).
 *
 * What we deliberately did NOT carry over from the old send():
 *   - mobile fire-and-forget + history polling (the iOS keepalive hack)
 *   - typing-animation pacing (typewriter is a separate composable)
 *   - tryRecover / dispatch.status retries (root cause of older bugs;
 *     see MEMORY.md 4/25)
 *   - perf telemetry (TTFT, tool counts) — telemetry comes later
 *
 * Errors surface as a single onError callback. Caller decides UX.
 */

import { apiUrl } from '@/api/_base'

export interface SseSendOpts {
  /** Required: chat / session id, also passed as OpenAI `user` field. */
  sid: string
  /** Required: full message list (caller decides history shape). */
  messages: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>
  /** Optional model override; server picks default if omitted. */
  model?: string
  /** Path override (tests). Defaults to `/v2/api/copilot/stream`. */
  url?: string
  /** Per-chunk timeout. Defaults to 30_000ms. 0 disables. */
  chunkTimeoutMs?: number
}

export interface SseHandlers {
  onDelta: (text: string) => void
  onDone: () => void
  /** Called once on terminal failure (network, http, parse, timeout, abort). */
  onError: (err: SseError) => void
}

export type SseErrorKind =
  | 'network'        // fetch threw / DNS / offline
  | 'http'           // non-2xx response
  | 'timeout'        // no chunks within chunkTimeoutMs
  | 'aborted'        // user-initiated abort
  | 'unknown'

export interface SseError {
  kind: SseErrorKind
  message: string
  status?: number
}

export interface SseStreamHandle {
  /** Promise resolves after onDone or onError has fired. */
  done: Promise<void>
  abort: () => void
}

/**
 * Open an SSE stream and pump frames into the supplied handlers.
 *
 * Pure function — no Vue reactivity, no DOM. Callers (composables /
 * components) wire deltas into their own state.
 */
export function openSseStream(
  opts: SseSendOpts,
  handlers: SseHandlers,
): SseStreamHandle {
  const ctrl = new AbortController()
  const url = opts.url ?? apiUrl('/copilot/stream')
  const chunkTimeoutMs = opts.chunkTimeoutMs ?? 30_000
  let aborted = false
  let finished = false
  let activeReader: ReadableStreamDefaultReader<Uint8Array> | null = null

  const abort = () => {
    if (finished) return
    aborted = true
    ctrl.abort()
    // Some runtimes (jsdom in particular) don't propagate AbortSignal
    // into a body reader created from `response.body`. Cancel it
    // explicitly so the read loop unblocks immediately.
    if (activeReader) {
      try { void activeReader.cancel() } catch { /* noop */ }
    }
  }

  function finish(err: SseError | null): void {
    if (finished) return
    finished = true
    if (err) handlers.onError(err)
    else handlers.onDone()
  }

  const done = (async () => {
    let res: Response
    try {
      res = await fetch(url, {
        method: 'POST',
        signal: ctrl.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: opts.model,
          stream: true,
          user: opts.sid,
          messages: opts.messages,
        }),
      })
    } catch (e: unknown) {
      if (aborted) return finish({ kind: 'aborted', message: 'aborted' })
      const msg = e instanceof Error ? e.message : String(e)
      return finish({ kind: 'network', message: msg })
    }

    if (!res.ok) {
      return finish({
        kind: 'http',
        message: `HTTP ${res.status}`,
        status: res.status,
      })
    }
    if (!res.body) {
      return finish({ kind: 'unknown', message: 'no response body' })
    }

    const reader = res.body.getReader()
    activeReader = reader
    const decoder = new TextDecoder()
    let buf = ''
    let timer: ReturnType<typeof setTimeout> | null = null

    const armTimeout = () => {
      if (chunkTimeoutMs <= 0) return
      if (timer) clearTimeout(timer)
      timer = setTimeout(() => {
        // No new chunk for chunkTimeoutMs — give up.
        try { reader.cancel() } catch { /* noop */ }
        finish({ kind: 'timeout', message: `no chunk for ${chunkTimeoutMs}ms` })
      }, chunkTimeoutMs)
    }

    armTimeout()

    try {
      while (true) {
        const { done: rDone, value } = await reader.read()
        if (rDone) break
        if (aborted) break
        armTimeout()
        buf += decoder.decode(value, { stream: true })
        // SSE frames separated by \n; keep incomplete trailer in `buf`.
        const lines = buf.split('\n')
        buf = lines.pop() ?? ''
        for (const rawLine of lines) {
          const line = rawLine.trimEnd()
          if (!line.startsWith('data: ')) continue
          const data = line.slice(6)
          if (data === '[DONE]') {
            if (timer) clearTimeout(timer)
            return finish(null)
          }
          try {
            const parsed = JSON.parse(data) as {
              choices?: Array<{ delta?: { content?: string } }>
            }
            const delta = parsed.choices?.[0]?.delta?.content
            if (typeof delta === 'string' && delta.length > 0) {
              handlers.onDelta(delta)
            }
          } catch {
            // Malformed frame — legacy parser also swallows these.
          }
        }
      }
      if (timer) clearTimeout(timer)
      if (aborted) return finish({ kind: 'aborted', message: 'aborted' })
      // Stream ended without explicit [DONE]; treat as successful close.
      return finish(null)
    } catch (e: unknown) {
      if (timer) clearTimeout(timer)
      if (aborted) return finish({ kind: 'aborted', message: 'aborted' })
      const msg = e instanceof Error ? e.message : String(e)
      return finish({ kind: 'network', message: msg })
    }
  })()

  return { done, abort }
}
