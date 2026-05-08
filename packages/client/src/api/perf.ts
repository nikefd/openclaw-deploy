import { apiUrl } from './_base'
// Phase E1 — perf API. Tries /api/perf/{summary,log} on the v2 server (proxy
// to perf-api on :7687, which exposes /api/perf/{stats,logs}). The upstream
// payloads have a quite different shape than the v2 dashboard wants, so when
// we get a real response we still merge in fixture endpoint/latency arrays
// that the upstream doesn't compute. A proper transform lives in Phase E4.

import {
  FIXTURE_ENDPOINTS,
  FIXTURE_ERRORS,
  FIXTURE_LATENCY_24H,
  FIXTURE_SUMMARY,
  type EndpointMetric,
  type ErrorEntry,
  type LatencyBucket,
  type PerfSummary,
  type TimeWindow,
} from '@/fixtures/perf'

export interface PerfSummaryResponse {
  window: TimeWindow
  summary: PerfSummary
  endpoints: EndpointMetric[]
  latency: LatencyBucket[]
}

function fixtureSummary(window: TimeWindow): PerfSummaryResponse {
  const scale = window === '1h' ? 0.05 : window === '6h' ? 0.25 : window === '7d' ? 7 : 1
  return {
    window,
    summary: { ...FIXTURE_SUMMARY, totalRequests: Math.round(FIXTURE_SUMMARY.totalRequests * scale) },
    endpoints: FIXTURE_ENDPOINTS.map((e) => ({ ...e, count: Math.max(1, Math.round(e.count * scale)) })),
    latency: FIXTURE_LATENCY_24H,
  }
}

interface UpstreamStats {
  totalEntries: number
  byType: Record<string, { count: number; totalMs: number; avg: number; p50: number; p95: number; p99: number }>
}

export async function fetchPerfSummary(window: TimeWindow = '24h'): Promise<PerfSummaryResponse> {
  try {
    const r = await fetch(apiUrl('/perf/summary?window=' + window), { credentials: 'include' })
    if (!r.ok) throw new Error(`http ${r.status}`)
    const body = (await r.json()) as UpstreamStats | { fallback?: boolean }
    if ('fallback' in body && body.fallback) return fixtureSummary(window)
    const stats = body as UpstreamStats
    if (typeof stats.totalEntries !== 'number') return fixtureSummary(window)
    const http = stats.byType.http
    const fb = fixtureSummary(window)
    return {
      window,
      summary: {
        ...fb.summary,
        totalRequests: stats.totalEntries,
        avgMs: http?.avg ?? fb.summary.avgMs,
        p95Ms: http?.p95 ?? fb.summary.p95Ms,
      },
      endpoints: fb.endpoints,
      latency: fb.latency,
    }
  } catch {
    return fixtureSummary(window)
  }
}

export async function fetchPerfErrors(window: TimeWindow = '24h', pattern = ''): Promise<ErrorEntry[]> {
  void window
  // Upstream perf-api doesn't expose an "errors" endpoint, so this stays on
  // the fixture for now.
  const list = pattern
    ? FIXTURE_ERRORS.filter((e) => e.endpoint.toLowerCase().includes(pattern.toLowerCase()))
    : FIXTURE_ERRORS
  return list
}
