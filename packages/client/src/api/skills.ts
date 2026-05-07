// api/skills.ts — Phase C2 stub. Phase E will hit /api/skills which lists the
// real skill registry.
export interface SkillSummary {
  id: string
  name: string
  description: string
  emoji: string
}

const STUB: SkillSummary[] = [
  {
    id: 'weather',
    name: 'weather',
    description: '查实时天气与多日预报（wttr.in / Open-Meteo）',
    emoji: '🌤️',
  },
  {
    id: 'github',
    name: 'github',
    description: 'GitHub issues / PRs / CI runs（gh CLI）',
    emoji: '🐙',
  },
  {
    id: 'discord',
    name: 'discord',
    description: 'Discord 消息与通道操作',
    emoji: '💬',
  },
  {
    id: 'company-duediligence',
    name: 'company-duediligence',
    description: '私有公司尽调，融资 / 团队 / 流量 / 合规交叉核查',
    emoji: '🔎',
  },
  {
    id: 'resume-gen',
    name: 'resume-gen',
    description: '基于基础简历针对 JD 生成定制版 PDF',
    emoji: '📄',
  },
]

export async function fetchSkills(): Promise<SkillSummary[]> {
  await new Promise((r) => setTimeout(r, 50))
  return STUB
}
