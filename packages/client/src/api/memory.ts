// api/memory.ts — Phase C2 stub. Phase E will replace with a real fetch to
// /api/memory/summary that reads MEMORY.md sections.
export interface MemorySection {
  id: string
  title: string
  preview: string
  /** epoch ms */
  updatedAt: number
}

const STUB: MemorySection[] = [
  {
    id: 'identity',
    title: 'IDENTITY',
    preview: '狗蛋 — 接地气、随和、偶尔贱兮兮的 AI 助手',
    updatedAt: Date.now() - 86_400_000,
  },
  {
    id: 'projects',
    title: 'Active Projects',
    preview: 'zhangyangbin.com chat 重构 v2，Phase A/B/C 进行中',
    updatedAt: Date.now() - 3 * 86_400_000,
  },
  {
    id: 'climbing-plan',
    title: 'Climbing Training',
    preview: '当前瓶颈 5.11d，每周 2 次 finger board + 拉伸',
    updatedAt: Date.now() - 7 * 86_400_000,
  },
  {
    id: 'finance',
    title: 'Finance Dashboard Notes',
    preview: 'NDX/BTC daily snapshot，watchlist 在 /finance 页',
    updatedAt: Date.now() - 14 * 86_400_000,
  },
  {
    id: 'lessons',
    title: 'Lessons Learned',
    preview: 'localStorage 配额溢出会吃掉异常 — 写入要 try/catch',
    updatedAt: Date.now() - 30 * 86_400_000,
  },
]

export async function fetchMemorySummary(): Promise<MemorySection[]> {
  // Simulate the network round-trip so the UI's loading branch gets exercised.
  await new Promise((r) => setTimeout(r, 50))
  return STUB
}
