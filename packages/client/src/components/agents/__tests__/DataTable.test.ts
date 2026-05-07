import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DataTable, { type Column } from '@/components/agents/DataTable.vue'

interface Row {
  name: string
  qty: number
  [k: string]: unknown
}

const COLS: Column<Row>[] = [
  { key: 'name', label: 'Name' },
  { key: 'qty', label: 'Qty', align: 'right' },
]

const ROWS: Row[] = [
  { name: 'Charlie', qty: 30 },
  { name: 'Alpha', qty: 10 },
  { name: 'Bravo', qty: 20 },
]

// vue-tsc cannot propagate component generics through @vue/test-utils' mount()
// signature, so we cast through `unknown` to silence the resulting `Column<T>`
// vs `Column<unknown>` mismatch. Runtime behaviour is unaffected.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const Comp = DataTable as any

describe('DataTable', () => {
  it('renders rows in original order without sort', () => {
    const w = mount(Comp, { props: { columns: COLS, rows: ROWS } })
    const cells = w.findAll('tbody tr td:first-child').map((c) => c.text())
    expect(cells).toEqual(['Charlie', 'Alpha', 'Bravo'])
  })

  it('respects initialSortKey + initialSortDir', () => {
    const w = mount(Comp, {
      props: {
        columns: COLS,
        rows: ROWS,
        initialSortKey: 'qty',
        initialSortDir: 'desc',
      },
    })
    const cells = w.findAll('tbody tr td:first-child').map((c) => c.text())
    expect(cells).toEqual(['Charlie', 'Bravo', 'Alpha'])
  })

  it('toggles sort direction when same header clicked twice', async () => {
    const w = mount(Comp, { props: { columns: COLS, rows: ROWS } })
    const headers = w.findAll('th')
    await headers[0].trigger('click')
    let cells = w.findAll('tbody tr td:first-child').map((c) => c.text())
    expect(cells).toEqual(['Alpha', 'Bravo', 'Charlie'])

    await headers[0].trigger('click')
    cells = w.findAll('tbody tr td:first-child').map((c) => c.text())
    expect(cells).toEqual(['Charlie', 'Bravo', 'Alpha'])
  })

  it('sorts numerically when column values are numbers', async () => {
    const w = mount(Comp, { props: { columns: COLS, rows: ROWS } })
    const headers = w.findAll('th')
    await headers[1].trigger('click')
    const qcells = w.findAll('tbody tr td:nth-child(2)').map((c) => c.text())
    expect(qcells).toEqual(['10', '20', '30'])
  })
})
