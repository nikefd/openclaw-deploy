// fixtures/memory.ts — Phase E3 fallback when /api/memory/* is unreachable.
// Real data is served by packages/server (see routes/memory.ts).

import type { MemoryEntry, MemoryFile } from '@/api/memory'

const day = 86_400_000
const t0 = Date.now()

export const FIXTURE_MEMORY_ENTRIES: MemoryEntry[] = [
  {
    path: 'MEMORY.md',
    name: 'MEMORY.md',
    sizeBytes: 4096,
    mtime: t0 - 1 * day,
    preview: '长期记忆：项目状态、习惯、偏好…',
    group: 'top',
  },
  {
    path: 'SOUL.md',
    name: 'SOUL.md',
    sizeBytes: 1800,
    mtime: t0 - 5 * day,
    preview: '人设：狗蛋，接地气、随和、偶尔贱兮兮',
    group: 'top',
  },
  {
    path: 'USER.md',
    name: 'USER.md',
    sizeBytes: 920,
    mtime: t0 - 7 * day,
    preview: '斌哥，北京，UTC+8，说中文风格随意',
    group: 'top',
  },
  {
    path: 'IDENTITY.md',
    name: 'IDENTITY.md',
    sizeBytes: 480,
    mtime: t0 - 7 * day,
    preview: '名字：狗蛋，emoji 🐶',
    group: 'top',
  },
  {
    path: 'AGENTS.md',
    name: 'AGENTS.md',
    sizeBytes: 9600,
    mtime: t0 - 2 * day,
    preview: '工作目录约定、heartbeat 行为、安全守则',
    group: 'top',
  },
  {
    path: 'HEARTBEAT.md',
    name: 'HEARTBEAT.md',
    sizeBytes: 320,
    mtime: t0 - 0.5 * day,
    preview: '心跳清单：邮件 / 日历 / 提醒',
    group: 'top',
  },
  {
    path: 'memory/2026-05-01.md',
    name: '2026-05-01.md',
    sizeBytes: 4096,
    mtime: t0 - 1 * day,
    preview: '今天搞定 Phase D 合并，agents hub 上线…',
    group: 'memory',
  },
  {
    path: 'memory/2026-04-30.md',
    name: '2026-04-30.md',
    sizeBytes: 6500,
    mtime: t0 - 2 * day,
    preview: '梳理 v2 重构剩余阶段，E1/E2/E3 拆分',
    group: 'memory',
  },
]

export const FIXTURE_MEMORY_CONTENT: Record<string, MemoryFile> = Object.fromEntries(
  FIXTURE_MEMORY_ENTRIES.map((e) => [
    e.path,
    {
      path: e.path,
      mtime: e.mtime,
      content: `# ${e.name}\n\n_(fixture fallback — server unreachable)_\n\n${e.preview}\n`,
    } satisfies MemoryFile,
  ]),
)
