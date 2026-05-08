/**
 * @oc/gateway — Unified API Gateway (7700)
 * 
 * Single entry point for all backend services:
 * - Chat / Files (file-api 7682)
 * - Finance (7684)
 * - Agents (7685)
 * - Usage (7686)
 * - Perf (7687)
 */

import http from 'node:http'
import express from 'express'
import cors from 'cors'
import type { Request, Response, NextFunction } from 'express'

const PORT = Number(process.env.API_GATEWAY_PORT ?? 7700)
const app = express()

// Middleware
app.use(cors({ origin: '*', credentials: true }))
app.use(express.json({ limit: '100mb' }))
app.use(express.urlencoded({ limit: '100mb', extended: true }))

// Request logging
app.use((req: Request, res: Response, next: NextFunction) => {
  const start = Date.now()
  res.on('finish', () => {
    const ms = Date.now() - start
    const status = res.statusCode >= 400 ? `❌ ${res.statusCode}` : `✓ ${res.statusCode}`
    // eslint-disable-next-line no-console
    console.log(`[${new Date().toISOString()}] ${status} ${req.method.padEnd(6)} ${req.path.padEnd(50)} ${ms}ms`)
  })
  next()
})

// ============================================================
// Proxy function
// ============================================================
async function proxyToUpstream(
  req: Request,
  res: Response,
  upstreamBase: string,
  pathPrefix: string,
) {
  const url = new URL(`${pathPrefix}${req.path}`, upstreamBase)
  
  // Copy query params
  for (const [key, value] of Object.entries(req.query ?? {})) {
    url.searchParams.append(key, String(value))
  }
  
  const headers: Record<string, string> = {
    'content-type': req.get('content-type') || 'application/json',
  }
  if (req.get('cookie')) headers.cookie = String(req.get('cookie'))
  if (req.get('authorization')) headers.authorization = String(req.get('authorization'))
  
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5000)
    
    const upstream = await fetch(url.toString(), {
      method: req.method,
      headers,
      body: req.method !== 'GET' ? JSON.stringify(req.body) : undefined,
      signal: controller.signal,
    })
    
    clearTimeout(timer)
    
    const text = await upstream.text()
    res.status(upstream.status)
    res.set('content-type', upstream.headers.get('content-type') || 'application/json')
    res.send(text)
  } catch (err: unknown) {
    console.error(`[PROXY ERROR] ${req.method} ${upstreamBase}${pathPrefix}${req.path}:`, (err as Error).message)
    res.status(502).json({ error: 'upstream unavailable', reason: (err as Error).message })
  }
}

// ============================================================
// Routes
// ============================================================

// File API (7682)
app.use('/api/chat', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7682', '/api/chat'))
app.use('/api/chats', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7682', '/api/chats'))
app.use('/api/copilot', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7682', '/api/copilot'))
app.use('/api/files', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7682', '/api/files'))

// Finance API (7684)
app.use('/api/finance', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7684', '/api/finance'))

// Agents API (7685)
app.use('/api/agents', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7685', '/api/agents'))

// Usage API (7686)
app.use('/api/usage', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7686', '/api/usage'))

// Perf API (7687)
app.use('/api/perf', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7687', '/api/perf'))

// Health
app.get('/healthz', (_req: Request, res: Response) => {
  res.json({ ok: true, port: PORT, service: 'api-gateway' })
})

app.all('/health', (_req: Request, res: Response) => {
  res.json({ ok: true })
})

// 404
app.use((_req: Request, res: Response) => {
  res.status(404).json({ error: 'not found' })
})

// Error handler
app.use((err: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error('[ERROR]', err.message)
  res.status(500).json({ error: err.message || 'internal server error' })
})

http.createServer(app).listen(PORT, '0.0.0.0', () => {
  // eslint-disable-next-line no-console
  console.log(`🌐 API Gateway listening on http://0.0.0.0:${PORT}`)
})
