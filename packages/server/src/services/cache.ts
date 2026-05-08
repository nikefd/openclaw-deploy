/**
 * cache.ts — In-memory cache with TTL support
 *
 * Provides a simple but effective caching layer for frequently accessed data
 * like chat lists. Uses TTL (time-to-live) to automatically invalidate stale data.
 *
 * Architecture: Cache layer → business logic → API responses
 */

export interface CacheEntry<T> {
  data: T
  timestamp: number
  ttl: number
}

export interface CacheOptions {
  ttl?: number // milliseconds
  maxSize?: number // max entries
}

export class Cache<T = unknown> {
  private store: Map<string, CacheEntry<T>> = new Map()
  private defaultTtl: number
  private maxSize: number

  constructor(opts: CacheOptions = {}) {
    this.defaultTtl = opts.ttl ?? 30 * 1000 // 30 seconds default
    this.maxSize = opts.maxSize ?? 1000
  }

  /**
   * Get value from cache if valid (not expired)
   */
  get(key: string): T | null {
    const entry = this.store.get(key)
    if (!entry) return null

    // Check if expired
    const age = Date.now() - entry.timestamp
    if (age > entry.ttl) {
      this.store.delete(key)
      return null
    }

    return entry.data
  }

  /**
   * Set value in cache with TTL
   */
  set(key: string, data: T, ttl?: number): void {
    // Evict oldest if at max size
    if (this.store.size >= this.maxSize) {
      const firstKey = this.store.keys().next().value
      if (firstKey) this.store.delete(firstKey)
    }

    this.store.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttl ?? this.defaultTtl,
    })
  }

  /**
   * Check if key exists and is valid
   */
  has(key: string): boolean {
    return this.get(key) !== null
  }

  /**
   * Delete specific key
   */
  delete(key: string): void {
    this.store.delete(key)
  }

  /**
   * Clear all cache
   */
  clear(): void {
    this.store.clear()
  }

  /**
   * Get cache size
   */
  size(): number {
    return this.store.size
  }

  /**
   * Get or compute — if key exists and valid, return it; otherwise compute and cache
   */
  async getOrCompute<R>(
    key: string,
    compute: () => Promise<R>,
    ttl?: number,
  ): Promise<R> {
    const cached = this.get(key) as R | null
    if (cached) return cached

    const result = await compute()
    this.set(key, result as unknown as T, ttl)
    return result
  }
}

/**
 * Global cache instances for different data types
 */
export const cacheManager = {
  chats: new Cache({ ttl: 30 * 1000, maxSize: 500 }), // 30s TTL, max 500 entries
  skills: new Cache({ ttl: 60 * 1000, maxSize: 100 }),
  memory: new Cache({ ttl: 60 * 1000, maxSize: 100 }),
}
