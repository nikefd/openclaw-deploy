import http from 'node:http'
import express from 'express'
import cors from 'cors'
import { Server as IOServer } from 'socket.io'
import type { ClientToServer, ServerToClient } from '@oc/shared/events'
import { attachChatStream } from './services/chat-stream.js'
import { createLegacyRouter } from './routes/legacy.js'
import { createMemoryRouter } from './routes/memory.js'
import { createSkillsRouter } from './routes/skills.js'
import { createChatsRouter } from './routes/chats.js'
import { createCopilotRouter } from './routes/copilot.js'
import { errorHandler } from './middleware/error-handler.js'
import { requestLogger, slowQueryLogger } from './middleware/request-logger.js'
import { limiters } from './middleware/rate-limiter.js'
import { createHealthRouter } from './routes/health.js'

const PORT = Number(process.env.PORT ?? 8001)
const ALLOWED_ORIGINS = [
  'http://localhost:5174',
  'http://127.0.0.1:5174',
]

const app = express()
app.use(cors({ origin: ALLOWED_ORIGINS, credentials: true }))
app.use(express.json({ limit: '2mb' }))

// Logging middleware (early in chain)
app.use(requestLogger)
app.use(slowQueryLogger(2000)) // warn if slower than 2s

// Rate limiting (before routes)
app.use('/api/copilot/stream', limiters.strict.middleware()) // 10/min for LLM calls
app.use('/api/', limiters.normal.middleware()) // 100/min for other APIs

// Add request ID to all requests for tracing
app.use((req, res, next) => {
  res.locals.requestId = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  next()
})

app.get('/healthz', (_req, res) => {
  res.json({ ok: true, phase: 'b' })
})

// Health check endpoint for mobile reconnection
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: Date.now() })
})

// Phase E1: legacy adapter — proxy /api/* through to the existing Node
// services (file-api 7682 / finance 7684 / agents 7685 / usage 7686 /
// perf 7687). See routes/legacy.ts for the endpoint reality table.
app.use(createLegacyRouter())

// Phase E2a: chat persistence + SSE forward to legacy file-api (7682).
// We do NOT re-implement chat storage — file-api owns the disk files
// and the old UI still writes to it directly. We're just the entrypoint
// nginx routes /v2/api/chats/* and /v2/api/copilot/stream to.
app.use(createChatsRouter())

// DEBUG: log all requests before copilot router
app.use((req, res, next) => {
  if (req.path.includes('copilot')) {
    // eslint-disable-next-line no-console
    console.log(`[DEBUG-COPILOT] ${req.method} ${req.path}`)
  }
  next()
})

app.use(createCopilotRouter())

// Phase E3: memory + skills panels.
app.use('/api/memory', createMemoryRouter())
app.use('/api/skills', createSkillsRouter())

// Phase E4: health checks and observability
app.use(createHealthRouter())

const httpServer = http.createServer(app)

const io = new IOServer<ClientToServer, ServerToClient>(httpServer, {
  cors: {
    origin: ALLOWED_ORIGINS,
    credentials: true,
  },
})

// Phase B: attach the /chat-run namespace.
attachChatStream(io)

// Default-namespace connections are still logged for diagnostics.
io.on('connection', (socket) => {
  // eslint-disable-next-line no-console
  console.log(`[socket.io] connect id=${socket.id}`)
  socket.on('disconnect', (reason) => {
    // eslint-disable-next-line no-console
    console.log(`[socket.io] disconnect id=${socket.id} reason=${reason}`)
  })
})

// Error handler middleware (must be last)
app.use(errorHandler)

httpServer.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[@oc/server] phase B comms listening on http://127.0.0.1:${PORT}`)
})
