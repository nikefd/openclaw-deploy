/**
 * Health check and observability routes
 *
 * Provides:
 * - /health — liveness probe
 * - /ready — readiness probe
 * - /metrics — performance metrics
 * - /diagnostics — detailed diagnostics
 */

import express from 'express'
import type { Request, Response } from 'express'

/**
 * Create health check router
 */
export function createHealthRouter() {
  const router = express.Router()

  /**
   * GET /health
   * Liveness probe: is the service running?
   */
  router.get('/health', (_req: Request, res: Response) => {
    res.json({
      status: 'ok',
      timestamp: Date.now(),
      uptime: process.uptime(),
    })
  })

  /**
   * GET /ready
   * Readiness probe: is the service ready to handle requests?
   */
  router.get('/ready', (_req: Request, res: Response) => {
    // Check if all dependencies are available
    const checks = {
      memory: checkMemory(),
      disk: checkDisk(),
      handlers: true, // Routes registered
    }

    const allReady = Object.values(checks).every((v) => v === true)

    if (allReady) {
      res.json({
        status: 'ready',
        timestamp: Date.now(),
        checks,
      })
    } else {
      res.status(503).json({
        status: 'not-ready',
        timestamp: Date.now(),
        checks,
      })
    }
  })

  /**
   * GET /metrics
   * Performance and operational metrics
   */
  router.get('/metrics', (_req: Request, res: Response) => {
    const memUsage = process.memoryUsage()
    const cpuUsage = process.cpuUsage()

    res.json({
      timestamp: Date.now(),
      uptime: process.uptime(),
      memory: {
        heapUsed: Math.round(memUsage.heapUsed / 1024 / 1024), // MB
        heapTotal: Math.round(memUsage.heapTotal / 1024 / 1024),
        external: Math.round(memUsage.external / 1024 / 1024),
        rss: Math.round(memUsage.rss / 1024 / 1024),
      },
      cpu: {
        user: cpuUsage.user,
        system: cpuUsage.system,
      },
      process: {
        pid: process.pid,
        version: process.version,
        platform: process.platform,
      },
    })
  })

  /**
   * GET /diagnostics
   * Detailed diagnostics for troubleshooting
   */
  router.get('/diagnostics', (_req: Request, res: Response) => {
    const memUsage = process.memoryUsage()

    res.json({
      timestamp: Date.now(),
      version: '1.0.0', // From package.json
      environment: process.env.NODE_ENV || 'development',
      uptime: process.uptime(),
      memory: {
        heapUsed: memUsage.heapUsed,
        heapTotal: memUsage.heapTotal,
        external: memUsage.external,
        rss: memUsage.rss,
        heapUsedPercent: (memUsage.heapUsed / memUsage.heapTotal) * 100,
      },
      resources: {
        cpuUsage: process.cpuUsage(),
        limits: {
          maxListeners: require('events').EventEmitter.defaultMaxListeners,
        },
      },
      runtime: {
        v8: process.versions.v8,
        node: process.versions.node,
      },
    })
  })

  return router
}

/**
 * Check memory health
 */
function checkMemory(): boolean {
  const memUsage = process.memoryUsage()
  const heapUsedPercent = (memUsage.heapUsed / memUsage.heapTotal) * 100

  // Alert if heap usage > 90%
  if (heapUsedPercent > 90) {
    console.warn(`[HEALTH] High memory usage: ${heapUsedPercent.toFixed(1)}%`)
    return false
  }

  return true
}

/**
 * Check disk health (simplified)
 */
function checkDisk(): boolean {
  // In production, check actual disk space
  // For now, assume OK if we can write to temp
  try {
    const tmpPath = require('os').tmpdir()
    require('fs').accessSync(tmpPath)
    return true
  } catch {
    return false
  }
}

/**
 * Metrics collector for middleware integration
 */
export class MetricsCollector {
  private metrics = {
    requests: {
      total: 0,
      success: 0,
      error: 0,
      slow: 0,
    },
    latency: {
      min: Infinity,
      max: 0,
      avg: 0,
      sum: 0,
    },
  }

  recordRequest(status: number, duration: number): void {
    this.metrics.requests.total++

    if (status >= 200 && status < 400) {
      this.metrics.requests.success++
    } else if (status >= 400) {
      this.metrics.requests.error++
    }

    if (duration > 2000) {
      this.metrics.requests.slow++
    }

    // Latency tracking
    this.metrics.latency.min = Math.min(this.metrics.latency.min, duration)
    this.metrics.latency.max = Math.max(this.metrics.latency.max, duration)
    this.metrics.latency.sum += duration
    this.metrics.latency.avg = this.metrics.latency.sum / this.metrics.requests.total
  }

  getMetrics() {
    return {
      ...this.metrics,
      successRate: ((this.metrics.requests.success / this.metrics.requests.total) * 100).toFixed(1),
      slowRate: ((this.metrics.requests.slow / this.metrics.requests.total) * 100).toFixed(1),
    }
  }

  reset(): void {
    this.metrics = {
      requests: { total: 0, success: 0, error: 0, slow: 0 },
      latency: { min: Infinity, max: 0, avg: 0, sum: 0 },
    }
  }
}

export const metricsCollector = new MetricsCollector()
