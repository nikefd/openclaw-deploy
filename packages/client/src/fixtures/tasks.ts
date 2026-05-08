// fixtures/tasks.ts — Phase D2 stub data for the Tasks board.
// 20 entries covering all status × runtime buckets so the filters have
// something to do. Real data comes from /api/tasks/list later.

export type TaskStatus = 'running' | 'done' | 'failed' | 'pending'
export type TaskRuntime = 'short' | 'medium' | 'long' // ≤5min / ≤30min / >30min

export interface TaskFixture {
  runId: string
  sessionKey: string
  parent: string | null
  label: string
  status: TaskStatus
  startedAt: number // epoch ms
  endedAt: number | null
  durationMs: number // for running tasks: now - startedAt
  tokensIn: number
  tokensOut: number
  model: string
  children: string[]
  timeline: Array<{ ts: number; kind: 'spawn' | 'tool' | 'message' | 'done' | 'error'; text: string }>
}

const NOW = Date.now()
const MIN = 60_000
const HOUR = 60 * MIN

function mk(
  i: number,
  status: TaskStatus,
  durationMs: number,
  label: string,
  opts: Partial<TaskFixture> = {},
): TaskFixture {
  const startedAt = NOW - durationMs - i * 30_000
  const endedAt = status === 'running' || status === 'pending' ? null : startedAt + durationMs
  return {
    runId: `run_${1000 + i}`,
    sessionKey: `agent:opus:subagent:${(i * 7919).toString(16)}`,
    parent: i % 4 === 0 ? null : `run_${1000 + Math.max(0, i - 1)}`,
    label,
    status,
    startedAt,
    endedAt,
    durationMs,
    tokensIn: 1200 + i * 230,
    tokensOut: 400 + i * 90,
    model: ['claude-opus-4.7', 'claude-haiku-4', 'gpt-5', 'glm-5'][i % 4]!,
    children: i % 5 === 0 ? [`run_${2000 + i}`, `run_${2001 + i}`] : [],
    timeline: [
      { ts: startedAt, kind: 'spawn', text: `任务启动: ${label}` },
      { ts: startedAt + Math.floor(durationMs * 0.3), kind: 'tool', text: '调用 read / exec' },
      { ts: startedAt + Math.floor(durationMs * 0.7), kind: 'message', text: '中间输出 …' },
      ...(status === 'done'
        ? [{ ts: endedAt!, kind: 'done' as const, text: '完成' }]
        : status === 'failed'
          ? [{ ts: endedAt!, kind: 'error' as const, text: '失败：超时 / 异常' }]
          : []),
    ],
    ...opts,
  }
}

export const STUB_TASKS: TaskFixture[] = [
  // running × short
  mk(0, 'running', 2 * MIN, 'phase-d2: 看板 + usage + arch'),
  mk(1, 'running', 4 * MIN, 'gh-issues: 拉取 #128'),
  // running × medium
  mk(2, 'running', 12 * MIN, 'company-duediligence: ACME Inc'),
  mk(3, 'running', 22 * MIN, 'resume-gen: senior swe @ Stripe'),
  // running × long
  mk(4, 'running', 45 * MIN, 'long-running: nightly memory compaction'),
  // done × short
  mk(5, 'done', 90_000, 'weather: 北京未来 3 天'),
  mk(6, 'done', 3 * MIN, 'github: list PRs --label review'),
  // done × medium
  mk(7, 'done', 8 * MIN, 'discord: 总结 #general 今日'),
  mk(8, 'done', 18 * MIN, 'taskflow: inbox triage 12 messages'),
  mk(9, 'done', 25 * MIN, 'healthcheck: ufw + ssh + apt'),
  // done × long
  mk(10, 'done', 38 * MIN, 'video-frames: 提取 4K 直播切片'),
  mk(11, 'done', 1.2 * HOUR, 'skill-creator: 重构 finance-agent skill'),
  mk(12, 'done', 2.5 * HOUR, '每周 memory rollup'),
  // failed × short
  mk(13, 'failed', 45_000, 'gh-issues: rate-limited'),
  mk(14, 'failed', 2 * MIN, 'tmux: pane lookup failed'),
  // failed × medium
  mk(15, 'failed', 14 * MIN, 'browser-automation: captcha 卡住'),
  mk(16, 'failed', 22 * MIN, 'finance: 数据源 5xx'),
  // failed × long
  mk(17, 'failed', 50 * MIN, 'tts: ElevenLabs 长音频超时'),
  // pending
  mk(18, 'pending', 0, '待启动: nightly stock-pick'),
  mk(19, 'pending', 0, '待启动: 月度 token usage 汇总'),
]

export function bucketRuntime(durationMs: number): TaskRuntime {
  if (durationMs <= 5 * MIN) return 'short'
  if (durationMs <= 30 * MIN) return 'medium'
  return 'long'
}
