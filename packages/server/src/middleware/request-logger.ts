/**
 * request-logger.ts — Request/response logging middleware
 *
 * Logs all HTTP requests with timing, status, and performance metrics.
 * Useful for debugging and identifying slow endpoints.
 *
 * Format: [timestamp] [method] [path] [status] [duration]ms
 */

import type { Request, Response, NextFunction } from 'express'

export interface RequestMetrics {
  method: string
  path: string
  status: number
  duration: number
  timestamp: string
  requestId?: string
}

/**
 * Simple structured logging
 */
function logRequest(metrics: RequestMetrics): void {
  const { timestamp, method, path, status, duration, requestId } = metrics
  const statusColor = status >= 400 ? '❌' : status >= 300 ? '⚠️' : '✓'
  const reqId = requestId ? ` [${requestId}]` : ''
  // eslint-disable-next-line no-console
  console.log(
    `[${timestamp}] ${statusColor} ${method.padEnd(6)} ${path.padEnd(40)} ${String(status).padEnd(3)} ${duration}ms${reqId}`,
  )
}

/**
 * Request logging middleware
 * Tracks timing and logs results
 */
export function requestLogger(req: Request, res: Response, next: NextFunction): void {
  const startTime = Date.now()
  const requestId = res.locals?.requestId

  // Capture the original res.send to log after response is sent
  const originalSend = res.send
  res.send = function (data: any) {
    const duration = Date.now() - startTime
    const metrics: RequestMetrics = {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration,
      timestamp: new Date().toISOString(),
      requestId,
    }

    logRequest(metrics)

    // Call original send
    return originalSend.call(this, data)
  }

  next()
}

/**
 * Slow query logger — logs requests that take longer than threshold
 */
export function slowQueryLogger(thresholdMs: number = 1000) {
  return (req: Request, res: Response, next: NextFunction) => {
    const startTime = Date.now()

    const originalSend = res.send
    res.send = function (data: any) {
      const duration = Date.now() - startTime

      if (duration > thresholdMs) {
        // eslint-disable-next-line no-console
        console.warn(
          `[SLOW] ${req.method} ${req.path} took ${duration}ms (threshold: ${thresholdMs}ms)`,
        )
      }

      return originalSend.call(this, data)
    }

    next()
  }
}
