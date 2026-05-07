/**
 * copilot.ts — Phase E2a SSE streaming pipe.
 *
 * /api/copilot/stream is implemented today by file-api on :7682. It does
 * three jobs the v2 server intentionally does NOT replicate:
 *   1. Speaks to gateway :18789, holds the upstream connection.
 *   2. Streams chunks back to the caller as they arrive (no buffering).
 *   3. Persists the assistant message to ~/.openclaw/chats/<id>.json
 *      (debounced + atomic rename) — even if the client disconnects mid-stream,
 *      the upstream read continues and the final message lands on disk.
 *
 * Re-implementing any of that here would mean two writers fighting over the
 * same JSON file. So this route is pure pipe: forward the request to 7682,
 * stream the response body back unchanged, and on client abort cancel our
 * own fetch — file-api keeps reading and persisting (its stream handler
 * does not abort on response-write failure).
 *
 * We deliberately do NOT touch the JSON body. The shape is
 * { chatId, model, messages, agentId } (sniffed from the legacy UI) and may
 * grow; transparently passing the bytes means we don't need to keep this
 * file in lock-step with frontend changes.
 */

import express, { type Request, type Response as ExResponse, type Router } from 'express'

const FILE_API_BASE = 'http://127.0.0.1:7682'
// SSE streams are slow; the timeout only guards the *connect* phase. Once the
// upstream starts emitting bytes we reset/clear it and let the stream run
// for as long as the model takes (can be minutes).
const CONNECT_TIMEOUT_MS = 10_000

export interface CreateCopilotRouterOpts {
  fetchImpl?: typeof fetch
  upstreamBase?: string
  /** Connect timeout override (tests). */
  connectTimeoutMs?: number
}

export function createCopilotRouter(opts: CreateCopilotRouterOpts = {}): Router {
  const router = express.Router()
  const base = opts.upstreamBase ?? FILE_API_BASE
  const connectTimeoutMs = opts.connectTimeoutMs ?? CONNECT_TIMEOUT_MS
  const doFetch = opts.fetchImpl ?? fetch

  router.post('/api/copilot/stream', async (req: Request, res: ExResponse) => {
    // express.json already parsed the body. Re-serialize for the upstream
    // request — the payload is small ({chatId, model, messages[], agentId})
    // so the cost is negligible and we avoid reading the raw stream twice.
    const body = JSON.stringify(req.body ?? {})

    const headers: Record<string, string> = {
      'content-type': 'application/json',
    }
    if (req.headers.cookie) headers.cookie = String(req.headers.cookie)
    if (req.headers.accept) headers.accept = String(req.headers.accept)

    const controller = new AbortController()
    const connectTimer = setTimeout(() => controller.abort(), connectTimeoutMs)

    // If the caller closes the connection, abort our upstream fetch too. The
    // upstream service (file-api) keeps reading from gateway and finishes
    // writing to disk regardless — we verified this in the legacy stack.
    const onClientClose = () => controller.abort()
    req.on('close', onClientClose)

    let upstream: Response
    try {
      upstream = (await doFetch(`${base}/api/copilot/stream`, {
        method: 'POST',
        headers,
        body,
        signal: controller.signal,
      })) as Response
    } catch (err) {
      clearTimeout(connectTimer)
      req.off('close', onClientClose)
      // Don't 500 — the legacy frontend treats non-2xx as a hard error and
      // shows it to the user. 502 mirrors the chats router style.
      if (!res.headersSent) {
        const aborted = (err as { name?: string } | null)?.name === 'AbortError'
        res.status(502).json({
          error: aborted ? 'upstream_timeout' : 'upstream_unreachable',
        })
      }
      return
    }
    // First byte received — connect phase done.
    clearTimeout(connectTimer)

    // Mirror status + relevant headers (especially content-type=text/event-stream
    // and any X-Upstream-* timing headers the legacy UI reads for perf logs).
    res.status(upstream.status)
    upstream.headers.forEach((value, key) => {
      // Hop-by-hop / managed-by-node headers shouldn't be forwarded.
      const k = key.toLowerCase()
      if (
        k === 'content-length' ||
        k === 'transfer-encoding' ||
        k === 'connection' ||
        k === 'keep-alive'
      ) {
        return
      }
      res.setHeader(key, value)
    })
    // SSE-friendly defaults — disable nginx buffering when the proxy is in
    // front and force chunked transfer.
    if (!res.getHeader('cache-control')) res.setHeader('cache-control', 'no-cache')
    res.setHeader('x-accel-buffering', 'no')

    // No upstream body — just end with the status (e.g. file-api returned 400
    // "chatId required").
    if (!upstream.body) {
      const text = await upstream.text()
      req.off('close', onClientClose)
      res.send(text)
      return
    }

    // Pump the upstream stream into the response without buffering.
    const reader = upstream.body.getReader()
    try {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        if (value && value.byteLength > 0) {
          // res.write returns false if the kernel buffer is full; we don't
          // need backpressure here because Node will queue and SSE chunks
          // are tiny (<=8KB). For very large uploads we'd want drain handling.
          res.write(Buffer.from(value))
        }
      }
    } catch (err) {
      // Client closed or upstream errored. Either way we just stop writing
      // to the response — file-api continues persisting on its own.
      // (Don't rethrow: would crash the request handler.)
      void err
    } finally {
      req.off('close', onClientClose)
      try {
        res.end()
      } catch {
        /* response already torn down */
      }
    }
  })

  return router
}
