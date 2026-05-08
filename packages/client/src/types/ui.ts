/**
 * UI-only types for Phase C1. Domain types live in @oc/shared.
 */

import type { ChatMessage } from '@oc/shared/chat'

export type ThemeMode = 'dark' | 'light'

export interface MessageBubbleProps {
  message: ChatMessage
  /** When true the bubble is currently receiving streaming deltas (assistant only). */
  streaming?: boolean
  /** When provided + streaming, replaces message text with this live buffer. */
  streamingText?: string
}

export interface MessageListProps {
  messages: ChatMessage[]
  streamingDelta?: string
  isStreaming?: boolean
}

export interface ChatPaneProps {
  sid: string
  modelLabel?: string
}

export interface ChatRecord {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
}
