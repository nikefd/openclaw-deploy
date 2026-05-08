/**
 * error-handler.ts — Unified error handling middleware
 *
 * All errors from routes/services are caught here, logged with structured format,
 * assigned a unique error ID for tracing, and returned as standardized responses.
 *
 * Architecture: Express middleware (error handler) → structured logging → standardized JSON response
 */

import type { ErrorRequestHandler } from 'express'

export interface AppError extends Error {
  statusCode?: number
  errorId?: string
  context?: Record<string, unknown>
}

/**
 * Generate a simple unique ID for error tracing
 */
function generateErrorId(): string {
  return `err_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

export class HttpError extends Error implements AppError {
  statusCode: number
  errorId: string
  context: Record<string, unknown>

  constructor(
    statusCode: number,
    message: string,
    context?: Record<string, unknown>,
  ) {
    super(message)
    this.statusCode = statusCode
    this.errorId = generateErrorId()
    this.context = context ?? {}
    this.name = 'HttpError'
  }
}

/**
 * Structured logging function
 * Format: [LEVEL] [errorId] message context
 */
function logError(level: string, errorId: string, message: string, context?: Record<string, unknown>): void {
  const timestamp = new Date().toISOString()
  const contextStr = context ? ` ${JSON.stringify(context)}` : ''
  // eslint-disable-next-line no-console
  console.error(`[${timestamp}] [${level}] [${errorId}] ${message}${contextStr}`)
}

/**
 * Standardized error response format
 */
interface ErrorResponse {
  error: {
    id: string
    status: number
    message: string
    timestamp: string
  }
}

/**
 * Express error handler middleware
 * Should be attached last via app.use()
 */
export const errorHandler: ErrorRequestHandler = (err, req, res, _next) => {
  const error = err as AppError
  const errorId = error.errorId ?? generateErrorId()
  const statusCode = error.statusCode ?? 500
  const message = error.message ?? 'Internal Server Error'

  logError('ERROR', errorId, message, {
    path: req.path,
    method: req.method,
    ...error.context,
  })

  const response: ErrorResponse = {
    error: {
      id: errorId,
      status: statusCode,
      message,
      timestamp: new Date().toISOString(),
    },
  }

  res.status(statusCode).json(response)
}

/**
 * Async route wrapper to catch errors and pass to error handler
 * Usage: router.get('/path', asyncHandler(async (req, res) => { ... }))
 */
export function asyncHandler(
  fn: (req: any, res: any, next: any) => Promise<void>,
) {
  return (req: any, res: any, next: any) => {
    Promise.resolve(fn(req, res, next)).catch(next)
  }
}
