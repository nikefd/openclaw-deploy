/**
 * api/chat-socket.ts
 *
 * Singleton Socket.IO client bound to the `/chat-run` namespace on @oc/server.
 * Returned with strongly-typed event signatures from @oc/shared.
 *
 * Reconnection is enabled by default; the useChatStream composable is what
 * actually drives `resume(sid, lastSeq)` after a reconnect succeeds.
 */

import { io, type Socket } from 'socket.io-client'
import type { ClientToServer, ServerToClient } from '@oc/shared/events'

export type ChatSocket = Socket<ServerToClient, ClientToServer>

let _socket: ChatSocket | null = null

export function getChatSocket(): ChatSocket {
  if (_socket) return _socket
  // Same-origin in prod; vite dev proxies /socket.io -> :8001.
  _socket = io('/chat-run', {
    autoConnect: false,
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 500,
    reconnectionDelayMax: 5000,
    transports: ['websocket', 'polling'],
  })
  return _socket
}

/** Imperatively close & forget the singleton (HMR / tests). */
export function resetChatSocket(): void {
  if (_socket) {
    _socket.removeAllListeners()
    _socket.disconnect()
    _socket = null
  }
}
