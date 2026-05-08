/**
 * rate-limiter.ts — Request rate limiting middleware
 *
 * Prevents abuse by limiting requests per IP per time window.
 * Uses simple in-memory store (可升级到 Redis).
 *
 * Architecture: Track IP → check quota → reject or allow → update counter
 */

import type { Request, Response, NextFunction } from 'express'

export interface RateLimitConfig {
  windowMs: number // time window in milliseconds
  maxRequests: number // max requests per window
  keyGenerator?: (req: Request) => string // custom key (default: IP)
}

interface RateLimitEntry {
  count: number
  resetTime: number
}

export class RateLimiter {
  private store: Map<string, RateLimitEntry> = new Map()
  private windowMs: number
  private maxRequests: number
  private keyGenerator: (req: Request) => string

  constructor(config: RateLimitConfig) {
    this.windowMs = config.windowMs
    this.maxRequests = config.maxRequests
    this.keyGenerator = config.keyGenerator ?? this.defaultKeyGenerator
  }

  private defaultKeyGenerator(req: Request): string {
    return (
      (req.ip ??
        req.socket.remoteAddress ??
        req.headers['x-forwarded-for'] ??
        '127.0.0.1') as string
    )
  }

  /**
   * Check if request is allowed
   * Returns { allowed: boolean, remaining: number, resetTime: number }
   */
  check(req: Request): { allowed: boolean; remaining: number; resetTime: number } {
    const key = this.keyGenerator(req)
    const now = Date.now()

    let entry = this.store.get(key)

    // Entry expired or doesn't exist
    if (!entry || now > entry.resetTime) {
      entry = {
        count: 0,
        resetTime: now + this.windowMs,
      }
      this.store.set(key, entry)
    }

    const allowed = entry.count < this.maxRequests
    const remaining = Math.max(0, this.maxRequests - entry.count - 1)

    if (allowed) {
      entry.count++
    }

    return {
      allowed,
      remaining,
      resetTime: entry.resetTime,
    }
  }

  /**
   * Middleware factory
   */
  middleware() {
    return (req: Request, res: Response, next: NextFunction) => {
      const check = this.check(req)

      // Set headers
      res.setHeader('X-RateLimit-Limit', String(this.maxRequests))
      res.setHeader('X-RateLimit-Remaining', String(check.remaining))
      res.setHeader('X-RateLimit-Reset', String(Math.ceil(check.resetTime / 1000)))

      if (!check.allowed) {
        const retryAfter = Math.ceil((check.resetTime - Date.now()) / 1000)
        res.setHeader('Retry-After', String(retryAfter))
        return res.status(429).json({
          error: 'Too Many Requests',
          retryAfter,
        })
      }

      next()
    }
  }

  /**
   * Cleanup old entries periodically
   */
  cleanup(): void {
    const now = Date.now()
    for (const [key, entry] of this.store.entries()) {
      if (now > entry.resetTime + this.windowMs) {
        this.store.delete(key)
      }
    }
  }
}

/**
 * Pre-configured limiters
 */
export const limiters = {
  // Strict: 10 requests per minute
  strict: new RateLimiter({ windowMs: 60 * 1000, maxRequests: 10 }),

  // Normal: 100 requests per minute
  normal: new RateLimiter({ windowMs: 60 * 1000, maxRequests: 100 }),

  // Relaxed: 500 requests per 5 minutes
  relaxed: new RateLimiter({ windowMs: 5 * 60 * 1000, maxRequests: 500 }),
}

// Cleanup every 5 minutes
setInterval(() => {
  Object.values(limiters).forEach((limiter) => limiter.cleanup())
}, 5 * 60 * 1000)
