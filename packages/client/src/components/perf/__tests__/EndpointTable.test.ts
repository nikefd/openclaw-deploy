import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EndpointTable from '@/components/perf/EndpointTable.vue'
import type { EndpointMetric } from '@/fixtures/perf'

const rows: EndpointMetric[] = [
  { endpoint: 'GET /a', count: 10, avg: 50, p50: 40, p95: 100, p99: 200, errors: 0, trend: 'flat' },
  { endpoint: 'GET /b', count: 20, avg: 80, p50: 60, p95: 500, p99: 900, errors: 5, trend: 'up' },
  { endpoint: 'GET /c', count: 30, avg: 30, p50: 20, p95: 250, p99: 400, errors: 2, trend: 'down' },
]

describe('EndpointTable', () => {
  it('sorts by p95 desc by default', () => {
    const w = mount(EndpointTable, { props: { rows } })
    const eps = w.findAll('td.ep').map((c) => c.text())
    expect(eps).toEqual(['GET /b', 'GET /c', 'GET /a'])
  })

  it('clicking p95 header again toggles to ascending', async () => {
    const w = mount(EndpointTable, { props: { rows } })
    const headers = w.findAll('th')
    // headers: Endpoint, Count, Avg, P50, P95, P99, Err
    const p95Header = headers[4]!
    await p95Header.trigger('click')
    const eps = w.findAll('td.ep').map((c) => c.text())
    expect(eps).toEqual(['GET /a', 'GET /c', 'GET /b'])
  })

  it('sorts endpoint name ascending when clicked', async () => {
    const w = mount(EndpointTable, { props: { rows } })
    const headers = w.findAll('th')
    await headers[0]!.trigger('click') // endpoint
    const eps = w.findAll('td.ep').map((c) => c.text())
    expect(eps).toEqual(['GET /a', 'GET /b', 'GET /c'])
  })
})
