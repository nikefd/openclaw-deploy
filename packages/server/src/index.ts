import http from 'node:http'
import express from 'express'
import cors from 'cors'
import { Server as IOServer } from 'socket.io'
import type { ClientToServer, ServerToClient } from '@oc/shared/events'

const PORT = Number(process.env.PORT ?? 8001)
const ALLOWED_ORIGINS = [
  'http://localhost:5174',
  'http://127.0.0.1:5174',
]

const app = express()
app.use(cors({ origin: ALLOWED_ORIGINS, credentials: true }))
app.use(express.json({ limit: '2mb' }))

app.get('/healthz', (_req, res) => {
  res.json({ ok: true, phase: 'a' })
})

const httpServer = http.createServer(app)

const io = new IOServer<ClientToServer, ServerToClient>(httpServer, {
  cors: {
    origin: ALLOWED_ORIGINS,
    credentials: true,
  },
})

// Phase A: just log connections. The /chat-run namespace + start/resume/abort
// handlers land in Phase B (see REFACTOR_V2.md §3 Phase B).
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
  console.log(`[@oc/server] phase A scaffold listening on http://127.0.0.1:${PORT}`)
})
