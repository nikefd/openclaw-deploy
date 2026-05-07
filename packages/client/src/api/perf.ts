// api/perf.ts — Phase D3 stub. Phase E will pull from /api/perf/*.
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

function delay<T>(value: T, ms = 30): Promise<T> {
  return new Promise((res) => setTimeout(() => res(value), ms))
}

export async function fetchPerfSummary(window: TimeWindow = '24h'): Promise<PerfSummaryResponse> {
  // Stub: scale numbers slightly by window so the UI looks alive.
  const scale = window === '1h' ? 0.05 : window === '6h' ? 0.25 : window === '7d' ? 7 : 1
  const summary: PerfSummary = {
    ...FIXTURE_SUMMARY,
    totalRequests: Math.round(FIXTURE_SUMMARY.totalRequests * scale),
  }
  const endpoints = FIXTURE_ENDPOINTS.map((e) => ({ ...e, count: Math.max(1, Math.round(e.count * scale)) }))
  return delay({ window, summary, endpoints, latency: FIXTURE_LATENCY_24H })
}

export async function fetchPerfErrors(window: TimeWindow = '24h', pattern = ''): Promise<ErrorEntry[]> {
  void window
  const list = pattern
    ? FIXTURE_ERRORS.filter((e) => e.endpoint.toLowerCase().includes(pattern.toLowerCase()))
    : FIXTURE_ERRORS
  return delay(list)
}
