const http = require('http')
const express = require('express')
const cors = require('cors')

const PORT = Number(process.env.API_GATEWAY_PORT ?? 7700)
const app = express()

app.use(cors({ origin: '*', credentials: true }))
app.use(express.json({ limit: '100mb' }))

app.use((req, res, next) => {
  const start = Date.now()
  res.on('finish', () => {
    const ms = Date.now() - start
    const status = res.statusCode >= 400 ? `❌ ${res.statusCode}` : `✓ ${res.statusCode}`
    console.log(`[${new Date().toISOString()}] ${status} ${req.method.padEnd(6)} ${req.path} ${ms}ms`)
  })
  next()
})

async function proxyToUpstream(req, res, upstreamBase, pathPrefix) {
  const url = new URL(`${pathPrefix}${req.path}`, upstreamBase)
  
  for (const [key, value] of Object.entries(req.query || {})) {
    url.searchParams.append(key, String(value))
  }
  
  const headers = {
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
  } catch (err) {
    console.error(`[PROXY ERROR] ${req.method} ${upstreamBase}${pathPrefix}${req.path}:`, err.message)
    res.status(502).json({ error: 'upstream unavailable', reason: err.message })
  }
}

app.get('/healthz', (req, res) => {
  res.json({ ok: true, port: PORT, service: 'api-gateway' })
})

app.use('/api/chat', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7682', '/api/chat'))
app.use('/api/chats', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7682', '/api/chats'))
app.use('/api/copilot', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7682', '/api/copilot'))
app.use('/api/files', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7682', '/api/files'))

app.use('/api/finance', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7684', '/api/finance'))
app.use('/api/agents', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7685', '/api/agents'))
app.use('/api/usage', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7686', '/api/usage'))
app.use('/api/perf', (req, res) => proxyToUpstream(req, res, 'http://127.0.0.1:7687', '/api/perf'))

app.use((req, res) => {
  res.status(404).json({ error: 'not found' })
})

app.use((err, req, res, next) => {
  console.error('[ERROR]', err.message)
  res.status(500).json({ error: err.message || 'internal server error' })
})

http.createServer(app).listen(PORT, '0.0.0.0', () => {
  console.log(`🌐 API Gateway listening on http://0.0.0.0:${PORT}`)
})
