/**
 * copilot.ts — Phase E2a SSE streaming pipe — NOW POINTS TO GATEWAY.
 *
 * /api/copilot/stream forwards requests to gateway :18789's streaming endpoint.
 * (file-api doesn't actually implement this route in the current codebase.)
 */

import express, { type Request, type Response as ExResponse, type Router } from 'express'

const GATEWAY_BASE = 'http://127.0.0.1:18789'
const CONNECT_TIMEOUT_MS = 60_000

export interface CreateCopilotRouterOpts {
  fetchImpl?: typeof fetch
  upstreamBase?: string
  connectTimeoutMs?: number
}

export function createCopilotRouter(opts: CreateCopilotRouterOpts = {}): Router {
  const router = express.Router()
  const base = opts.upstreamBase ?? GATEWAY_BASE
  const connectTimeoutMs = opts.connectTimeoutMs ?? CONNECT_TIMEOUT_MS
  const doFetch = opts.fetchImpl ?? fetch

  router.post('/api/copilot/stream', async (req: Request, res: ExResponse) => {
    const body = JSON.stringify(req.body ?? {})

    const headers: Record<string, string> = {
      'content-type': 'application/json',
      'authorization': 'Bearer 17043bad6b19491dfa222d681d43584fbc3e8dd3781edfbc',
    }
    if (req.headers.cookie) headers.cookie = String(req.headers.cookie)
    if (req.headers.accept) headers.accept = String(req.headers.accept)

    const controller = new AbortController()
    const connectTimer = setTimeout(() => controller.abort(), connectTimeoutMs)

    const onClientClose = () => controller.abort()
    res.on('close', onClientClose)

    let upstream: Response
    try {
      // Try gateway's streaming endpoint
      upstream = (await doFetch(`${base}/v1/responses`, {
        method: 'POST',
        headers,
        body,
        signal: controller.signal,
      })) as Response
    } catch (err) {
      clearTimeout(connectTimer)
      req.off('close', onClientClose)
      if (!res.headersSent) {
        const aborted = (err as { name?: string } | null)?.name === 'AbortError'
        res.status(502).json({
          error: aborted ? 'upstream_timeout' : 'upstream_unreachable',
        })
      }
      res.off('close', onClientClose)
      return
    }
    clearTimeout(connectTimer)

    res.status(upstream.status)
    upstream.headers.forEach((value, key) => {
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
    if (!res.getHeader('cache-control')) res.setHeader('cache-control', 'no-cache')
    res.setHeader('x-accel-buffering', 'no')

    if (!upstream.body) {
      const text = await upstream.text()
      res.off('close', onClientClose)
      res.send(text)
      return
    }

    const reader = upstream.body.getReader()
    try {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        if (value && value.byteLength > 0) {
          res.write(Buffer.from(value))
        }
      }
    } catch (err) {
      void err
    } finally {
      res.off('close', onClientClose)
      try {
        res.end()
      } catch {
        /* response already torn down */
      }
    }
  })

  return router
}
