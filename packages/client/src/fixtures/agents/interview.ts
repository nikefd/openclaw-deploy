// Phase D1 — interview prep stub data.
import type { InterviewDashboard, InterviewSchedule, CompanyCard, PrepProgress } from '@/api/interview'

export const IV_SCHEDULE: InterviewSchedule[] = [
  { date: '2026-05-08', time: '10:00', company: 'NVIDIA', round: 'Tech Phone', interviewer: 'Senior MLE', status: 'upcoming' },
  { date: '2026-05-09', time: '15:30', company: 'Pika', round: 'On-site Round 2', interviewer: 'Founding Eng', status: 'upcoming' },
  { date: '2026-05-10', time: '09:00', company: 'Tipsy', round: 'System Design', interviewer: 'Staff Eng', status: 'upcoming' },
  { date: '2026-05-12', time: '14:00', company: 'ShopBack', round: 'Behavioral', interviewer: 'EM', status: 'upcoming' },
  { date: '2026-05-13', time: '11:00', company: 'NVIDIA', round: 'Coding Round', interviewer: 'TBD', status: 'upcoming' },
]

export const IV_COMPANIES: CompanyCard[] = [
  { name: 'NVIDIA', emoji: '🟩', status: 'active', round: 'Tech Phone → Coding', lastTouch: '2026-05-05', notes: 'CUDA + ML infra 方向' },
  { name: 'Pika', emoji: '🎬', status: 'active', round: 'On-site Round 2/3', lastTouch: '2026-05-04', notes: '生成视频，硅谷' },
  { name: 'Tipsy', emoji: '🍸', status: 'active', round: 'System Design', lastTouch: '2026-05-03', notes: '社交 + AI app' },
  { name: 'ShopBack', emoji: '🛒', status: 'active', round: 'Behavioral', lastTouch: '2026-05-02', notes: '新加坡，cashback' },
  { name: 'Anthropic', emoji: '🤖', status: 'paused', round: 'Hold', lastTouch: '2026-04-20', notes: '等候补' },
  { name: 'OpenAI', emoji: '🧠', status: 'rejected', round: '——', lastTouch: '2026-04-15', notes: '初筛挂' },
]

export const IV_PROGRESS: PrepProgress[] = [
  { topic: '系统设计', done: 12, total: 20, note: 'DDIA 进度过半' },
  { topic: '行为面（STAR）', done: 8, total: 12, note: '需要补 conflict 题' },
  { topic: '编码题（LeetCode）', done: 87, total: 150, note: 'medium 节奏稳定' },
]

export const IV_DASHBOARD: InterviewDashboard = {
  schedule: IV_SCHEDULE,
  companies: IV_COMPANIES,
  progress: IV_PROGRESS,
}
