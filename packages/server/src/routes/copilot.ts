/**
 * copilot.ts — Stream LLM responses from Gateway
 * 
 * Gateway already returns SSE format, we just passthrough.
 */

import express, { type Request, type Response as ExResponse, type Router } from 'express'

const router = express.Router()
const GATEWAY_BASE = 'http://127.0.0.1:18789'
const GATEWAY_TOKEN = '17043bad6b19491dfa222d681d43584fbc3e8dd3781edfbc'
const CONNECT_TIMEOUT_MS = 60000

async function streamLLMResponse(req: Request, res: ExResponse) {
  const body = req.body ?? {}

  // Normalize model name to 'openclaw' (gateway requirement)
  if (body.model && !body.model.startsWith('openclaw')) {
    body.model = 'openclaw'
  }

  const bodyStr = JSON.stringify(body)
  const headers: Record<string, string> = {
    'content-type': 'application/json',
    'authorization': `Bearer ${GATEWAY_TOKEN}`,
  }

  console.log(`[copilot] POST /api/copilot/stream | model: ${body.model}`)

  let upstream: Response
  try {
    const controller = new AbortController()
    const connectTimer = setTimeout(() => controller.abort(), CONNECT_TIMEOUT_MS)
    const onClientClose = () => controller.abort()
    res.on('close', onClientClose)

    upstream = (await fetch(`${GATEWAY_BASE}/v1/chat/completions`, {
      method: 'POST',
      headers,
      body: bodyStr,
      signal: controller.signal,
    })) as Response

    clearTimeout(connectTimer)

    if (!upstream.ok) {
      const text = await upstream.text()
      console.error(`[copilot] Upstream error ${upstream.status}:`, text.slice(0, 200))
      res.status(upstream.status).send(text)
      res.off('close', onClientClose)
      return
    }

    res.setHeader('content-type', 'text/event-stream')
    res.setHeader('cache-control', 'no-cache')
    res.setHeader('x-accel-buffering', 'no')

    if (!upstream.body) {
      console.warn('[copilot] No response body')
      res.end()
      res.off('close', onClientClose)
      return
    }

    // Gateway returns SSE — passthrough directly
    const reader = upstream.body.getReader()
    try {
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        if (value && value.byteLength > 0) {
          res.write(Buffer.from(value))
        }
      }
    } finally {
      res.off('close', onClientClose)
      try {
        res.end()
      } catch {
        /* noop */
      }
    }
  } catch (err) {
    const msg = (err as Error).message
    console.error('[copilot] Error:', msg)
    res.status(502).json({ error: msg })
  }
}

router.post('/api/copilot/stream', streamLLMResponse)

export function createCopilotRouter(): Router {
  return router
}
