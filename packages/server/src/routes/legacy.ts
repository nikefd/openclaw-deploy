/**
 * legacy.ts — Phase E1 backend API adapter.
 *
 * Proxies the v2 server's /api/* routes to the existing legacy Node services
 * so the v2 frontend can stop using fixtures. We do NOT modify the upstream
 * services — they keep listening on their original ports.
 *
 * Upstream port map (probed 2026-05-07):
 *   7682 file-api    (services/file/server.js)
 *   7684 finance-api (finance-api-server.js)
 *   7685 agents-api  (services/agents/server.js)
 *   7686 usage-api   (services/usage/server.js)
 *   7687 perf-api    (services/perf/server.js)
 *
 * Endpoint reality check vs the spec brief:
 *   - The brief asked for /api/files/tree + /api/files/content. The real
 *     file-api exposes /api/files/list + /api/files/read. The adapter accepts
 *     the v2 names and rewrites them to the upstream names.
 *   - The brief asked for /api/perf/summary + /api/perf/log. The real perf-api
 *     exposes /api/perf/stats + /api/perf/logs (note plural). The adapter
 *     accepts the v2 names and rewrites.
 *   - The brief asked for /api/finance/holdings + /api/finance/signals. These
 *     do NOT exist on finance-api (probe → 404). We register them as
 *     placeholder routes that always return 503 + {fallback:true} so the
 *     frontend falls back to fixtures.
 *   - /api/ai-frontier/items does NOT exist on agents-api → placeholder 503.
 *   - /api/tasks/list does NOT exist on agents-api → placeholder 503.
 *   - The brief asked for /api/usage/summary?range=… The real usage-api
 *     exposes /api/usage. The adapter rewrites and forwards range as a query
 *     hint (upstream ignores it; the response shape stays the same).
 *   - /api/interview/schedule is served by reading the static JSON file at
 *     /var/www/chat/data/interview-schedule.json (no upstream service).
 *   - /api/agents/fitness/sessions is a straight pass-through.
 *
 * Error contract for callers:
 *   - Upstream 2xx → status + body forwarded verbatim (JSON re-serialized).
 *   - Upstream 4xx (non-404) → forwarded.
 *   - Upstream 5xx, network error, timeout, or "endpoint does not exist" →
 *     503 with body { error: '<reason>', fallback: true }.
 *   The frontend uses fallback:true (or just !res.ok) as the signal to load
 *   the local fixture.
 */

import type { Request, Response, Router } from 'express'
import express from 'express'
import { promises as fsp } from 'node:fs'

const DEFAULT_TIMEOUT_MS = 5000
const INTERVIEW_SCHEDULE_FILE = '/var/www/chat/data/interview-schedule.json'

export interface ProxyOptions {
  timeoutMs?: number
  /** Override the upstream URL builder for testing (default: identity). */
  fetchImpl?: typeof fetch
}

export interface UpstreamLike {
  status: number
  headers: Headers
  text(): Promise<string>
}

function buildUpstreamUrl(base: string, req: Request): string {
  // Rebuild the query string off Express' parsed query so we don't have to
  // reach into req.url (which can include the proxy path prefix).
  const u = new URL(base)
  for (const [k, v] of Object.entries(req.query)) {
    if (v == null) continue
    if (Array.isArray(v)) {
      for (const item of v) u.searchParams.append(k, String(item))
    } else {
      u.searchParams.append(k, String(v))
    }
  }
  return u.toString()
}

export async function proxyUpstream(
  upstreamUrl: string,
  req: Request,
  res: Response,
  opts: ProxyOptions = {},
): Promise<void> {
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const doFetch = opts.fetchImpl ?? fetch
  const target = buildUpstreamUrl(upstreamUrl, req)

  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let upstream: UpstreamLike | undefined
  try {
    const headers: Record<string, string> = {}
    const cookie = req.headers.cookie
    if (cookie) headers.cookie = cookie
    const accept = req.headers.accept
    if (accept) headers.accept = String(accept)
    upstream = (await doFetch(target, {
      method: 'GET',
      headers,
      signal: controller.signal,
    })) as unknown as UpstreamLike
  } catch (err) {
    clearTimeout(timer)
    const aborted = (err as { name?: string } | null)?.name === 'AbortError'
    res.status(503).json({
      error: aborted ? 'upstream_timeout' : 'upstream_unreachable',
      fallback: true,
    })
    return
  }
  clearTimeout(timer)

  // Treat upstream 5xx (and explicit 503/504) as "fall back to fixture".
  if (upstream.status >= 500) {
    res.status(503).json({
      error: 'upstream_error',
      upstreamStatus: upstream.status,
      fallback: true,
    })
    return
  }

  const body = await upstream.text()
  const contentType = upstream.headers.get('content-type') ?? 'application/json'
  res.status(upstream.status).type(contentType).send(body)
}

/** Always-fallback handler used for endpoints that do not exist upstream. */
function notImplemented(reason: string) {
  return (_req: Request, res: Response) => {
    res.status(503).json({ error: reason, fallback: true })
  }
}

export interface RegisterOpts {
  /** Override the global fetch (used by tests). */
  fetchImpl?: typeof fetch
  timeoutMs?: number
  /** Override interview-schedule file path (used by tests). */
  interviewScheduleFile?: string
}

/** Returns a Router with all Phase-E1 legacy adapter endpoints. */
export function createLegacyRouter(opts: RegisterOpts = {}): Router {
  const router = express.Router()
  const proxyOpts: ProxyOptions = {
    fetchImpl: opts.fetchImpl,
    timeoutMs: opts.timeoutMs,
  }
  const interviewFile = opts.interviewScheduleFile ?? INTERVIEW_SCHEDULE_FILE

  // ---- file-api (7682) ---------------------------------------------------
  // Brief: /api/files/tree + /api/files/content.
  // Reality: upstream is /api/files/list + /api/files/read. Rewrite.
  router.get('/api/files/tree', (req, res) =>
    proxyUpstream('http://127.0.0.1:7682/api/files/list', req, res, proxyOpts),
  )
  router.get('/api/files/content', (req, res) =>
    proxyUpstream('http://127.0.0.1:7682/api/files/read', req, res, proxyOpts),
  )

  // ---- perf-api (7687) ---------------------------------------------------
  // Brief: /api/perf/summary + /api/perf/log.
  // Reality: upstream is /api/perf/stats + /api/perf/logs (plural).
  router.get('/api/perf/summary', (req, res) =>
    proxyUpstream('http://127.0.0.1:7687/api/perf/stats', req, res, proxyOpts),
  )
  router.get('/api/perf/log', (req, res) =>
    proxyUpstream('http://127.0.0.1:7687/api/perf/logs', req, res, proxyOpts),
  )

  // ---- finance-api (7684) ------------------------------------------------
  router.get('/api/finance/dashboard', (req, res) =>
    proxyUpstream('http://127.0.0.1:7684/api/finance/dashboard', req, res, proxyOpts),
  )
  // Probed 404 → not implemented upstream. Always fallback.
  router.get('/api/finance/holdings', notImplemented('upstream_not_implemented'))
  router.get('/api/finance/signals', notImplemented('upstream_not_implemented'))

  // ---- agents-api (7685) -------------------------------------------------
  router.get('/api/agents/fitness/sessions', (req, res) =>
    proxyUpstream(
      'http://127.0.0.1:7685/api/agents/fitness/sessions',
      req,
      res,
      proxyOpts,
    ),
  )
  // Probed 404 → not implemented. Frontend should fallback.
  router.get('/api/ai-frontier/items', notImplemented('upstream_not_implemented'))
  router.get('/api/tasks/list', notImplemented('upstream_not_implemented'))

  // ---- usage-api (7686) --------------------------------------------------
  // Brief: /api/usage/summary. Reality: upstream is /api/usage AND it does an
  // exact `req.url === '/api/usage'` check (no query string), so we must NOT
  // forward our `range=` param to the upstream URL.
  router.get('/api/usage/summary', (req, res) => {
    // Build a synthetic request with empty query so proxyUpstream skips qs.
    const stripped = Object.create(req) as Request
    Object.defineProperty(stripped, 'query', { value: {}, configurable: true })
    return proxyUpstream('http://127.0.0.1:7686/api/usage', stripped, res, proxyOpts)
  })

  // ---- interview schedule (static file) ---------------------------------
  router.get('/api/interview/schedule', async (_req, res) => {
    try {
      const buf = await fsp.readFile(interviewFile, 'utf8')
      res.type('application/json').send(buf)
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code
      res
        .status(503)
        .json({ error: code === 'ENOENT' ? 'file_missing' : 'file_unreadable', fallback: true })
    }
  })

  return router
}
