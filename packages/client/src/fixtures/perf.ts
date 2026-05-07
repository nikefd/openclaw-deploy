// fixtures/perf.ts — Phase D3 stub perf metrics.
// 8 endpoints, 24h latency trend (24 buckets), 20 error log entries.

export interface EndpointMetric {
  endpoint: string
  count: number
  avg: number
  p50: number
  p95: number
  p99: number
  errors: number
  trend: 'up' | 'down' | 'flat'
}

export interface LatencyBucket {
  hour: number // 0..23 (relative)
  label: string
  p50: number
  p95: number
}

export interface ErrorEntry {
  ts: number
  endpoint: string
  status: number
  message: string
}

export interface PerfSummary {
  totalRequests: number
  totalRequestsTrend: 'up' | 'down' | 'flat'
  avgMs: number
  avgMsTrend: 'up' | 'down' | 'flat'
  p95Ms: number
  p95MsTrend: 'up' | 'down' | 'flat'
  p99Ms: number
  p99MsTrend: 'up' | 'down' | 'flat'
  errorRate: number // 0..1
  errorRateTrend: 'up' | 'down' | 'flat'
}

export const FIXTURE_SUMMARY: PerfSummary = {
  totalRequests: 18432,
  totalRequestsTrend: 'up',
  avgMs: 142,
  avgMsTrend: 'down',
  p95Ms: 480,
  p95MsTrend: 'flat',
  p99Ms: 1240,
  p99MsTrend: 'up',
  errorRate: 0.018,
  errorRateTrend: 'down',
}

export const FIXTURE_ENDPOINTS: EndpointMetric[] = [
  { endpoint: 'GET /api/chats', count: 4210, avg: 84, p50: 62, p95: 210, p99: 480, errors: 12, trend: 'down' },
  { endpoint: 'POST /api/chat-run', count: 3890, avg: 320, p50: 240, p95: 980, p99: 1840, errors: 41, trend: 'up' },
  { endpoint: 'GET /api/files/tree', count: 2145, avg: 56, p50: 40, p95: 140, p99: 280, errors: 3, trend: 'flat' },
  { endpoint: 'GET /api/files/content', count: 1820, avg: 92, p50: 70, p95: 240, p99: 520, errors: 8, trend: 'down' },
  { endpoint: 'GET /api/perf/summary', count: 1640, avg: 38, p50: 32, p95: 96, p99: 180, errors: 0, trend: 'flat' },
  { endpoint: 'GET /api/skills', count: 1280, avg: 44, p50: 36, p95: 110, p99: 220, errors: 1, trend: 'flat' },
  { endpoint: 'GET /api/memory', count: 1120, avg: 68, p50: 50, p95: 180, p99: 380, errors: 4, trend: 'up' },
  { endpoint: 'POST /auth/login', count: 320, avg: 156, p50: 120, p95: 420, p99: 980, errors: 18, trend: 'up' },
]

const PSEUDO = [
  72, 81, 65, 70, 88, 96, 110, 124, 140, 155, 168, 172, 180, 165, 150, 142, 134, 128, 120, 110, 96, 88, 78, 74,
]
const PSEUDO_P95 = [
  210, 240, 200, 220, 280, 320, 360, 400, 440, 480, 520, 540, 560, 510, 470, 450, 420, 400, 380, 350, 320, 290, 260, 240,
]

export const FIXTURE_LATENCY_24H: LatencyBucket[] = PSEUDO.map((p50, i) => ({
  hour: i,
  label: `${String(i).padStart(2, '0')}:00`,
  p50,
  p95: PSEUDO_P95[i] ?? p50 * 3,
}))

const ERROR_MSGS = [
  'connection reset',
  'upstream timeout',
  'invalid token',
  'rate limit exceeded',
  'unexpected EOF',
  'JSON parse error',
  'permission denied',
  'not found',
]

const ERROR_BASE = Date.parse('2026-05-01T08:00:00Z')
export const FIXTURE_ERRORS: ErrorEntry[] = Array.from({ length: 20 }, (_, i) => ({
  ts: ERROR_BASE - i * 90_000,
  endpoint: FIXTURE_ENDPOINTS[i % FIXTURE_ENDPOINTS.length]!.endpoint,
  status: [500, 502, 504, 401, 429, 400][i % 6]!,
  message: ERROR_MSGS[i % ERROR_MSGS.length]!,
}))

export type TimeWindow = '1h' | '6h' | '24h' | '7d'
