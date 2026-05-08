/**
 * pagination.ts — Pagination and field selection utilities
 *
 * Provides helpers for:
 * 1. Paginating large result sets
 * 2. Sparse fieldsets (客户端选择返回的字段)
 * 3. Filtering results
 *
 * Architecture: Query parsing → filtering/pagination → response formatting
 */

import type { Request } from 'express'

export interface PaginationParams {
  limit: number
  offset: number
}

export interface PaginationMeta {
  total: number
  count: number
  limit: number
  offset: number
  hasMore: boolean
}

/**
 * Parse pagination params from query string
 * ?limit=20&offset=0
 */
export function parsePaginationParams(req: Request): PaginationParams {
  let limit = parseInt(String(req.query.limit ?? '20'), 10)
  let offset = parseInt(String(req.query.offset ?? '0'), 10)

  // Constraints
  if (limit < 1) limit = 1
  if (limit > 100) limit = 100 // max 100 per request
  if (offset < 0) offset = 0

  return { limit, offset }
}

/**
 * Parse sparse fieldset from query string
 * ?fields=id,title,createdAt
 * Returns array of field names to include
 */
export function parseFields(req: Request): string[] | null {
  const fields = req.query.fields
  if (!fields || typeof fields !== 'string') return null

  return fields
    .split(',')
    .map((f) => f.trim())
    .filter((f) => f.length > 0)
}

/**
 * Filter object to only include specified fields
 */
export function selectFields<T extends Record<string, unknown>>(
  obj: T,
  fields: string[] | null,
): Partial<T> {
  if (!fields) return obj

  const result: Partial<T> = {}
  for (const field of fields) {
    if (field in obj) {
      result[field as keyof T] = obj[field as keyof T]
    }
  }
  return result
}

/**
 * Apply pagination to array
 */
export function paginate<T>(
  items: T[],
  params: PaginationParams,
): { items: T[]; meta: PaginationMeta } {
  const total = items.length
  const sliced = items.slice(params.offset, params.offset + params.limit)

  return {
    items: sliced,
    meta: {
      total,
      count: sliced.length,
      limit: params.limit,
      offset: params.offset,
      hasMore: params.offset + params.limit < total,
    },
  }
}

/**
 * Apply all transformations: filter, select fields, paginate
 */
export function transformList<T extends Record<string, unknown>>(
  items: T[],
  options: {
    fields?: string[] | null
    limit: number
    offset: number
  },
): { items: Partial<T>[]; meta: PaginationMeta } {
  // Paginate first
  const paginated = paginate(items, { limit: options.limit, offset: options.offset })

  // Then select fields
  const withFields = paginated.items.map((item) => selectFields(item, options.fields ?? null))

  return {
    items: withFields,
    meta: paginated.meta,
  }
}
