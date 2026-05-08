/**
 * Query optimization and analysis
 *
 * Monitors, analyzes, and suggests optimizations for:
 * - Slow queries
 * - N+1 query patterns
 * - Missing indexes
 * - Query complexity
 * - Cache-ability assessment
 */

export interface QueryMetric {
  query: string
  duration: number // ms
  timestamp: number
  cached: boolean
  rows: number
  status: 'success' | 'error' | 'timeout'
}

export interface QueryAnalysis {
  duration: number
  isSlow: boolean
  isN1Pattern: boolean
  cacheableScore: number // 0-100
  recommendations: string[]
}

export class QueryAnalyzer {
  private metrics: QueryMetric[] = []
  private maxMetrics = 1000
  private slowThreshold = 2000 // 2 seconds
  private readonly window = 60000 // 1 minute for pattern detection

  /**
   * Record a query execution
   */
  recordQuery(query: string, duration: number, rows: number, cached: boolean, status: 'success' | 'error' | 'timeout' = 'success'): void {
    this.metrics.push({
      query,
      duration,
      timestamp: Date.now(),
      cached,
      rows,
      status,
    })

    // Keep only recent metrics
    if (this.metrics.length > this.maxMetrics) {
      this.metrics = this.metrics.slice(-this.maxMetrics)
    }
  }

  /**
   * Analyze a query
   */
  analyze(query: string, duration: number, rows: number): QueryAnalysis {
    const now = Date.now()
    const recentQueries = this.metrics.filter((m) => now - m.timestamp < this.window)

    const isSlow = duration > this.slowThreshold
    const isN1 = this.detectN1Pattern(query, recentQueries)
    const cacheableScore = this.assessCacheability(query)

    const recommendations: string[] = []

    if (isSlow) {
      recommendations.push(`Query takes ${duration}ms (threshold: ${this.slowThreshold}ms)`)
      recommendations.push('Consider: adding index, pagination, or caching')
    }

    if (isN1) {
      recommendations.push('N+1 query pattern detected')
      recommendations.push('Consider: batch loading or JOIN optimization')
    }

    if (cacheableScore > 70) {
      recommendations.push(`High cache-ability (${cacheableScore}%) — consider caching`)
    }

    if (rows > 10000) {
      recommendations.push(`Result set large (${rows} rows) — consider pagination`)
    }

    return {
      duration,
      isSlow,
      isN1Pattern: isN1,
      cacheableScore,
      recommendations,
    }
  }

  /**
   * Detect N+1 query pattern (same query repeated many times)
   */
  private detectN1Pattern(query: string, recentQueries: QueryMetric[]): boolean {
    const similarQueries = recentQueries.filter((m) => this.querySimilarity(m.query, query) > 0.8)
    // If same query pattern appears >5 times in last minute, likely N+1
    return similarQueries.length > 5
  }

  /**
   * Simple query similarity check (0-1)
   */
  private querySimilarity(q1: string, q2: string): number {
    const n1 = this.normalizeQuery(q1)
    const n2 = this.normalizeQuery(q2)
    // Jaccard similarity of words
    const w1 = new Set(n1.split(' '))
    const w2 = new Set(n2.split(' '))
    const inter = new Set([...w1].filter((x) => w2.has(x)))
    const union = new Set([...w1, ...w2])
    return union.size === 0 ? 0 : inter.size / union.size
  }

  /**
   * Normalize query for comparison (remove IDs, timestamps)
   */
  private normalizeQuery(query: string): string {
    return query
      .replace(/\d+/g, 'N') // Replace numbers with N
      .replace(/'[^']*'/g, "'X'") // Replace string literals
      .toLowerCase()
  }

  /**
   * Assess if query result is cacheable
   * Score: 0-100 (higher = more cacheable)
   */
  private assessCacheability(query: string): number {
    let score = 50 // baseline

    // Good signs
    if (!query.includes('INSERT') && !query.includes('UPDATE') && !query.includes('DELETE')) {
      score += 30 // Read-only
    }
    if (query.includes('SELECT') && !query.includes('NOW()') && !query.includes('RAND()')) {
      score += 15 // Deterministic
    }
    if (!query.includes('OFFSET') || !query.includes('LIMIT')) {
      score += 5 // Not paginated
    }

    // Bad signs
    if (query.includes('OFFSET')) {
      score -= 10 // Pagination changes frequently
    }
    if (query.includes('LIMIT 1000') || query.includes('LIMIT 10000')) {
      score -= 15 // Large result set
    }

    return Math.max(0, Math.min(100, score))
  }

  /**
   * Get all slow queries from recent metrics
   */
  getSlowQueries(): QueryMetric[] {
    return this.metrics.filter((m) => m.duration > this.slowThreshold)
  }

  /**
   * Get query statistics
   */
  getStats() {
    const total = this.metrics.length
    if (total === 0) return null

    const avgDuration = this.metrics.reduce((sum, m) => sum + m.duration, 0) / total
    const maxDuration = Math.max(...this.metrics.map((m) => m.duration))
    const slowCount = this.metrics.filter((m) => m.duration > this.slowThreshold).length
    const cachedCount = this.metrics.filter((m) => m.cached).length
    const errorCount = this.metrics.filter((m) => m.status === 'error').length

    return {
      total,
      avgDuration,
      maxDuration,
      slowCount,
      slowPercentage: (slowCount / total) * 100,
      cachedCount,
      cacheHitRate: (cachedCount / total) * 100,
      errorCount,
      errorRate: (errorCount / total) * 100,
    }
  }

  /**
   * Clear metrics
   */
  reset(): void {
    this.metrics = []
  }
}

/**
 * Global query analyzer instance
 */
export const queryAnalyzer = new QueryAnalyzer()

/**
 * Example integration in request handler:
 *
 * app.get('/api/chats', async (req, res) => {
 *   const startTime = Date.now()
 *   try {
 *     const result = await fetchChats()
 *     const duration = Date.now() - startTime
 *
 *     const analysis = queryAnalyzer.analyze(
 *       'SELECT * FROM chats',
 *       duration,
 *       result.length
 *     )
 *
 *     if (analysis.recommendations.length > 0) {
 *       console.warn('Query suggestions:', analysis.recommendations)
 *     }
 *
 *     queryAnalyzer.recordQuery(
 *       'SELECT * FROM chats',
 *       duration,
 *       result.length,
 *       false,
 *       'success'
 *     )
 *
 *     res.json(result)
 *   } catch (err) {
 *     queryAnalyzer.recordQuery(
 *       'SELECT * FROM chats',
 *       Date.now() - startTime,
 *       0,
 *       false,
 *       'error'
 *     )
 *   }
 * })
 */
