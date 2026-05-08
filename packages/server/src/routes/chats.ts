/**
 * chats.ts — Phase E2a chat persistence reverse proxy.
 *
 * The legacy file-api on :7682 owns the canonical chat storage at
 * ~/.openclaw/chats/<id>.json (200+ existing files). The legacy chat UI at
 * /var/www/chat/index.html STILL writes through nginx → 7682 directly, so we
 * MUST NOT also write to the same files from this v2 server — that would be
 * a write-write race and could corrupt 200+ chats on disk.
 *
 * Instead: forward every /api/chats request to 7682. file-api stays the
 * single source of truth; we are just the entrypoint v2 nginx routes
 * /v2/api/chats/* to.
 *
 * Endpoint reality (probed 2026-05-07 against running 7682):
 *   GET    /api/chats         — list (supports ?full=1 and ?since=<ms>)
 *   GET    /api/chats/:id     — full chat doc
 *   PUT    /api/chats/:id     — write a single chat doc (also accepts POST
 *                               for sendBeacon compat)
 *   POST   /api/chats/:id     — same as PUT
 *   DELETE /api/chats/:id     — delete
 *
 * Cookie passthrough: file-api itself does not auth against the auth_token
 * cookie today, but we forward `cookie` anyway so any future authz on 7682
 * keeps working without a v2-server change.
 */

import express, { type Request, type Response as ExResponse, type Router } from 'express'
import { cacheManager } from '../services/cache.js'

const FILE_API_BASE = 'http://127.0.0.1:7682'
const DEFAULT_TIMEOUT_MS = 5000

export interface CreateChatsRouterOpts {
  /** Override fetch (tests). */
  fetchImpl?: typeof fetch
  /** Override upstream base (tests). */
  upstreamBase?: string
  timeoutMs?: number
}

/**
 * Forward a request to file-api and pipe the response back. Body is sent as
 * the raw collected JSON we already parsed (express.json was applied at the
 * app level, so req.body is the parsed object — we re-stringify for the
 * upstream call). For chat docs that is fine: the docs are JSON and not
 * larger than a few MB.
 *
 * Cache strategy:
 * - GET requests with no cache key collision → cache for 30s
 * - PUT/POST/DELETE → invalidate relevant cache entries
 */
async function forwardToFileApi(
  upstreamUrl: string,
  req: Request,
  res: ExResponse,
  opts: { fetchImpl?: typeof fetch; timeoutMs: number; cacheKey?: string },
): Promise<void> {
  const doFetch = opts.fetchImpl ?? fetch
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs)

  const headers: Record<string, string> = {}
  if (req.headers.cookie) headers.cookie = String(req.headers.cookie)
  if (req.headers.accept) headers.accept = String(req.headers.accept)

  let body: string | undefined
  if (req.method !== 'GET' && req.method !== 'DELETE' && req.method !== 'HEAD') {
    // express.json gave us a parsed object; serialize it back. If body was
    // empty (e.g. DELETE-shaped POST), skip.
    if (req.body && Object.keys(req.body).length > 0) {
      body = JSON.stringify(req.body)
      headers['content-type'] = 'application/json'
    }
  }

  let upstream: Response
  try {
    upstream = (await doFetch(upstreamUrl, {
      method: req.method,
      headers,
      body,
      signal: controller.signal,
    })) as Response
  } catch (err) {
    clearTimeout(timer)
    const aborted = (err as { name?: string } | null)?.name === 'AbortError'
    res.status(502).json({
      error: aborted ? 'upstream_timeout' : 'upstream_unreachable',
    })
    return
  }
  clearTimeout(timer)

  const text = await upstream.text()
  const ct = upstream.headers.get('content-type') ?? 'application/json'

  // Cache successful GET responses
  if (req.method === 'GET' && upstream.status === 200 && opts.cacheKey) {
    try {
      const data = JSON.parse(text)
      cacheManager.chats.set(opts.cacheKey, data)
    } catch {
      // ignore parse errors
    }
  }

  // Invalidate cache on mutations
  if (['PUT', 'POST', 'DELETE'].includes(req.method)) {
    cacheManager.chats.clear()
  }

  res.status(upstream.status).type(ct).send(text)
}

export function createChatsRouter(opts: CreateChatsRouterOpts = {}): Router {
  const router = express.Router()
  const base = opts.upstreamBase ?? FILE_API_BASE
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const fetchImpl = opts.fetchImpl

  // GET /api/chats — list with caching. Check cache first before hitting upstream.
  router.get('/api/chats', (req, res) => {
    const search = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : ''
    const cacheKey = `chats:list${search}` // include query in cache key

    // Try cache first
    const cached = cacheManager.chats.get(cacheKey)
    if (cached) {
      return res.json(cached)
    }

    // Not cached, forward to upstream and cache response
    return forwardToFileApi(`${base}/api/chats${search}`, req, res, {
      fetchImpl,
      timeoutMs,
      cacheKey,
    })
  })

  // POST /api/chats — legacy bulk save. Pass through unchanged.
  router.post('/api/chats', (req, res) =>
    forwardToFileApi(`${base}/api/chats`, req, res, { fetchImpl, timeoutMs }),
  )

  // GET /api/chats/:id — single chat with caching
  router.get('/api/chats/:id', (req, res) => {
    const cacheKey = `chats:${req.params.id}`
    const cached = cacheManager.chats.get(cacheKey)
    if (cached) {
      return res.json(cached)
    }

    return forwardToFileApi(
      `${base}/api/chats/${encodeURIComponent(req.params.id)}`,
      req,
      res,
      { fetchImpl, timeoutMs, cacheKey },
    )
  })

  // PUT /api/chats/:id — update (invalidates cache)
  router.put('/api/chats/:id', (req, res) =>
    forwardToFileApi(
      `${base}/api/chats/${encodeURIComponent(req.params.id)}`,
      req,
      res,
      { fetchImpl, timeoutMs },
    ),
  )

  // POST /api/chats/:id — update (invalidates cache)
  router.post('/api/chats/:id', (req, res) =>
    forwardToFileApi(
      `${base}/api/chats/${encodeURIComponent(req.params.id)}`,
      req,
      res,
      { fetchImpl, timeoutMs },
    ),
  )

  // DELETE /api/chats/:id — delete (invalidates cache)
  router.delete('/api/chats/:id', (req, res) =>
    forwardToFileApi(
      `${base}/api/chats/${encodeURIComponent(req.params.id)}`,
      req,
      res,
      { fetchImpl, timeoutMs },
    ),
  )

  return router
}
