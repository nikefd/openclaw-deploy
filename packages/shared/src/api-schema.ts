/**
 * REST API request/response schemas.
 *
 * Phase A: placeholder. Phase B will install `zod` and replace the type-only
 * stubs below with real `z.object(...)` runtime schemas + inferred types.
 *
 * Once zod is added:
 *   import { z } from 'zod'
 *   export const ChatCreateInput = z.object({ title: z.string().min(1).max(200) })
 *   export type ChatCreateInput = z.infer<typeof ChatCreateInput>
 */

// --- Stub types (no runtime validation yet) ---

export interface ChatCreateInput {
  title?: string
  meta?: Record<string, unknown>
}

export interface ChatCreateOutput {
  id: string
  title: string
  createdAt: number
}

export interface ChatSaveInput {
  id: string
  title?: string
  /** caller-supplied lastUpdatedAt for optimistic concurrency */
  expectedUpdatedAt?: number
}

export interface ChatSaveOutput {
  id: string
  updatedAt: number
}
