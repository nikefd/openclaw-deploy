import http from 'node:http'
import express from 'express'
import cors from 'cors'
import { Server as IOServer } from 'socket.io'
import type { ClientToServer, ServerToClient } from '@oc/shared/events'
import { attachChatStream } from './services/chat-stream.js'
import { createMemoryRouter } from './routes/memory.js'
import { createSkillsRouter } from './routes/skills.js'

const PORT = Number(process.env.PORT ?? 8001)
const ALLOWED_ORIGINS = [
  'http://localhost:5174',
  'http://127.0.0.1:5174',
]

const app = express()
app.use(cors({ origin: ALLOWED_ORIGINS, credentials: true }))
app.use(express.json({ limit: '2mb' }))

app.get('/healthz', (_req, res) => {
  res.json({ ok: true, phase: 'b' })
})

// Phase E3: memory + skills panels.
app.use('/api/memory', createMemoryRouter())
app.use('/api/skills', createSkillsRouter())

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

httpServer.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[@oc/server] phase B comms listening on http://127.0.0.1:${PORT}`)
})
