/**
 * Socket.IO event protocol shared between @oc/client and @oc/server.
 * Source of truth: REFACTOR_V2.md §2.
 *
 * Conventions:
 *   - sid       = chat session id (the "room" name on the server)
 *   - runId     = a single upstream run inside that session
 *   - seq       = monotonic sequence per-run, used by client's `lastSeq`
 *                 to replay missed events after reconnect.
 */

import type { ChatMessage, Usage } from './chat.js'

// ---------- Client -> Server ----------

export interface StartRunRequest {
  /** chat session id (room key) */
  sid: string
  /** the user-typed input that kicks off this run */
  input: string
  /** optional message history snapshot the client believes is current */
  history?: ChatMessage[]
  /** model override / agent profile */
  model?: string
  /** arbitrary client-supplied metadata */
  meta?: Record<string, unknown>
}

export interface ClientToServer {
  start: (req: StartRunRequest) => void
  resume: (sessionId: string, lastSeq?: number) => void
  abort: (sessionId: string) => void
}

// ---------- Server -> Client ----------

export interface RunQueuedEvent {
  sid: string
  runId: string
  seq: number
}

export interface RunStartedEvent {
  sid: string
  runId: string
  seq: number
}

export interface MessageDeltaEvent {
  sid: string
  runId: string
  delta: string
  seq: number
}

export interface ToolStartedEvent {
  sid: string
  tool: string
  seq: number
}

export interface ToolCompletedEvent {
  sid: string
  tool: string
  preview?: string
  seq: number
}

export interface RunCompletedEvent {
  sid: string
  runId: string
  output: string
  usage: Usage
  seq: number
}

export interface RunFailedEvent {
  sid: string
  runId: string
  error: string
  seq: number
}

export interface ServerToClient {
  'run.queued': (e: RunQueuedEvent) => void
  'run.started': (e: RunStartedEvent) => void
  'message.delta': (e: MessageDeltaEvent) => void
  'tool.started': (e: ToolStartedEvent) => void
  'tool.completed': (e: ToolCompletedEvent) => void
  'run.completed': (e: RunCompletedEvent) => void
  'run.failed': (e: RunFailedEvent) => void
}

/** Union of any server->client event payload (handy for repo persistence). */
export type AnyServerEvent =
  | ({ type: 'run.queued' } & RunQueuedEvent)
  | ({ type: 'run.started' } & RunStartedEvent)
  | ({ type: 'message.delta' } & MessageDeltaEvent)
  | ({ type: 'tool.started' } & ToolStartedEvent)
  | ({ type: 'tool.completed' } & ToolCompletedEvent)
  | ({ type: 'run.completed' } & RunCompletedEvent)
  | ({ type: 'run.failed' } & RunFailedEvent)
