// fixtures/skills.ts — Phase E3 fallback when /api/skills/* is unreachable.

import type { SkillEntry, SkillFile } from '@/api/skills'

export const FIXTURE_SKILL_ENTRIES: SkillEntry[] = [
  { name: 'company-duediligence', source: 'user', emoji: '🔎', description: '私有公司尽调（融资 / 团队 / 流量 / 合规交叉核查）', location: '~/.openclaw/skills/company-duediligence/SKILL.md' },
  { name: 'resume-gen', source: 'user', emoji: '📄', description: '基于基础简历针对 JD 生成定制版 PDF', location: '~/.openclaw/skills/resume-gen/SKILL.md' },
  { name: 'discord', source: 'builtin', emoji: '💬', description: 'Discord 操作（消息、通道）', location: '~/.npm-global/lib/node_modules/openclaw/skills/discord/SKILL.md' },
  { name: 'github', source: 'builtin', emoji: '🐙', description: 'GitHub issues / PRs / CI runs (gh CLI)', location: '~/.npm-global/lib/node_modules/openclaw/skills/github/SKILL.md' },
  { name: 'gh-issues', source: 'builtin', emoji: '🪲', description: '抓 issue 派子 agent 修，开 PR 跟踪', location: '~/.npm-global/lib/node_modules/openclaw/skills/gh-issues/SKILL.md' },
  { name: 'healthcheck', source: 'builtin', emoji: '🩺', description: '主机安全审计与硬化建议', location: '~/.npm-global/lib/node_modules/openclaw/skills/healthcheck/SKILL.md' },
  { name: 'weather', source: 'builtin', emoji: '☔', description: '查实时天气与多日预报（wttr.in / Open-Meteo）', location: '~/.npm-global/lib/node_modules/openclaw/skills/weather/SKILL.md' },
  { name: 'tmux', source: 'builtin', emoji: '🖥️', description: '远程操控 tmux 会话', location: '~/.npm-global/lib/node_modules/openclaw/skills/tmux/SKILL.md' },
]

export const FIXTURE_SKILL_CONTENT: Record<string, SkillFile> = Object.fromEntries(
  FIXTURE_SKILL_ENTRIES.map((e) => {
    const key = `${e.source}:${e.name}`
    return [
      key,
      {
        name: e.name,
        source: e.source,
        location: e.location,
        path: e.location,
        sizeBytes: 1024,
        mtime: Date.now(),
        content: `---\nname: ${e.name}\ndescription: ${e.description}\n---\n\n# ${e.name}\n\n_(fixture fallback — server unreachable)_\n\n${e.description}\n`,
      } satisfies SkillFile,
    ]
  }),
)
