/**
 * response-formatter.ts — Response formatting utilities
 *
 * Standardizes all API responses to a consistent format:
 * {
 *   data: <payload>,
 *   meta: { timestamp, requestId }
 * }
 *
 * Architecture: Response builder → consistent JSON structure → sent to client
 */

import type { Response } from 'express'

export interface ApiResponse<T = unknown> {
  data: T
  meta: {
    timestamp: string
    requestId?: string
  }
}

/**
 * Build standardized success response
 */
export function buildResponse<T>(
  data: T,
  requestId?: string,
): ApiResponse<T> {
  return {
    data,
    meta: {
      timestamp: new Date().toISOString(),
      requestId,
    },
  }
}

/**
 * Send standardized response
 */
export function sendResponse<T>(
  res: Response,
  data: T,
  statusCode: number = 200,
  requestId?: string,
): Response {
  return res.status(statusCode).json(buildResponse(data, requestId))
}

/**
 * Send paginated response
 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export function sendPaginated<T>(
  res: Response,
  items: T[],
  total: number,
  limit: number,
  offset: number,
  requestId?: string,
): Response {
  const paginated: PaginatedResponse<T> = {
    items,
    total,
    limit,
    offset,
  }
  return sendResponse(res, paginated, 200, requestId)
}
