// Phase D1 — climbing coach stub data.
import type { ClimbingDashboard, ClimbingSession } from '@/api/climbing'

const today = new Date()
function daysAgo(n: number): string {
  const d = new Date(today)
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

export const CLIMB_SESSIONS: ClimbingSession[] = [
  { date: daysAgo(0), gym: '问山', durationMin: 90, maxSend: 'V4', maxAttempt: 'V5', routes: 8, sendRate: 0.62 },
  { date: daysAgo(2), gym: '问山', durationMin: 75, maxSend: 'V3+', maxAttempt: 'V5', routes: 7, sendRate: 0.57 },
  { date: daysAgo(4), gym: '问山', durationMin: 100, maxSend: 'V4', maxAttempt: 'V5+', routes: 10, sendRate: 0.50 },
  { date: daysAgo(7), gym: '问山', durationMin: 80, maxSend: 'V4', maxAttempt: 'V5', routes: 9, sendRate: 0.66 },
  { date: daysAgo(9), gym: '问山', durationMin: 70, maxSend: 'V3+', maxAttempt: 'V4', routes: 6, sendRate: 0.83 },
  { date: daysAgo(11), gym: '岩时', durationMin: 95, maxSend: 'V4+', maxAttempt: 'V5', routes: 11, sendRate: 0.45 },
  { date: daysAgo(14), gym: '问山', durationMin: 85, maxSend: 'V3', maxAttempt: 'V4', routes: 8, sendRate: 0.75 },
  { date: daysAgo(16), gym: '问山', durationMin: 90, maxSend: 'V4', maxAttempt: 'V5', routes: 9, sendRate: 0.55 },
  { date: daysAgo(19), gym: '问山', durationMin: 70, maxSend: 'V3+', maxAttempt: 'V4+', routes: 7, sendRate: 0.71 },
  { date: daysAgo(22), gym: '岩时', durationMin: 100, maxSend: 'V4', maxAttempt: 'V5', routes: 10, sendRate: 0.50 },
  { date: daysAgo(25), gym: '问山', durationMin: 80, maxSend: 'V3+', maxAttempt: 'V4', routes: 8, sendRate: 0.62 },
  { date: daysAgo(28), gym: '问山', durationMin: 75, maxSend: 'V3', maxAttempt: 'V4', routes: 7, sendRate: 0.71 },
  { date: daysAgo(30), gym: '问山', durationMin: 90, maxSend: 'V4', maxAttempt: 'V5', routes: 9, sendRate: 0.55 },
  { date: daysAgo(33), gym: '问山', durationMin: 70, maxSend: 'V3+', maxAttempt: 'V4', routes: 6, sendRate: 0.83 },
  { date: daysAgo(36), gym: '岩时', durationMin: 85, maxSend: 'V3+', maxAttempt: 'V4+', routes: 8, sendRate: 0.50 },
  { date: daysAgo(39), gym: '问山', durationMin: 95, maxSend: 'V4', maxAttempt: 'V5', routes: 10, sendRate: 0.50 },
  { date: daysAgo(42), gym: '问山', durationMin: 80, maxSend: 'V3+', maxAttempt: 'V4', routes: 7, sendRate: 0.71 },
  { date: daysAgo(45), gym: '问山', durationMin: 70, maxSend: 'V3', maxAttempt: 'V4', routes: 6, sendRate: 0.83 },
  { date: daysAgo(48), gym: '岩时', durationMin: 100, maxSend: 'V4', maxAttempt: 'V5', routes: 11, sendRate: 0.45 },
  { date: daysAgo(52), gym: '问山', durationMin: 85, maxSend: 'V3+', maxAttempt: 'V4', routes: 8, sendRate: 0.62 },
]

export const CLIMB_DASHBOARD: ClimbingDashboard = {
  weeklyCount: 3,
  topGrade: 'V4+',
  redpointCount: 14,
  freqPerWeek: 2.4,
  bottleneck:
    '**核心瓶颈：脚法精度**\n\n最近 10 次训练中 V5 完成率仅 22%，主因为脚点选择不稳定，重心切换偏慢。\n\n建议：每次训练前 15 分钟做单脚静态绕点。',
  plan:
    '**本周训练计划**\n\n- 周二：耐力 4x4，V3 强度\n- 周四：bouldering 极限尝试 V5+\n- 周六：技术日，闭眼脚法 + silent feet\n- 周日：休息或低强度恢复',
  warmup:
    '**热身 + 拉伸（15 min）**\n\n1. 肩袖动态拉伸 3 min\n2. 手指 finger curl 2 min\n3. 髋关节开合 + 弓步 5 min\n4. 慢爬 V0–V1 热身路 5 min',
  sessions: CLIMB_SESSIONS,
}
