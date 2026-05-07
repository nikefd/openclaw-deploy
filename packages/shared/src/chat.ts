/**
 * Core chat domain types shared between client & server.
 * Phase A: minimal scaffolding — flesh out as Phase B/C consumes them.
 */

export type Role = 'user' | 'assistant' | 'system' | 'tool'

export interface TextBlock {
  type: 'text'
  text: string
}

export interface ImageBlock {
  type: 'image'
  url: string
  alt?: string
}

export interface ToolCallBlock {
  type: 'tool_call'
  tool: string
  input: unknown
  callId: string
}

export interface ToolResultBlock {
  type: 'tool_result'
  callId: string
  output: unknown
  preview?: string
}

export type ContentBlock = TextBlock | ImageBlock | ToolCallBlock | ToolResultBlock

export interface ChatMessage {
  id: string
  role: Role
  /** Unix ms */
  createdAt: number
  /** Mixed multi-modal content */
  content: ContentBlock[]
  /** Convenience flat text (concat of TextBlock parts) */
  text?: string
  /** Per-message usage if known */
  usage?: Usage
}

export interface Usage {
  promptTokens?: number
  completionTokens?: number
  totalTokens?: number
  /** Model that produced this run, if reported by upstream */
  model?: string
}

export interface ChatSession {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: ChatMessage[]
  meta?: Record<string, unknown>
}
