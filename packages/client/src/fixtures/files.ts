// fixtures/files.ts — Phase D3 stub directory tree (5 folders + 15 files).
// Mirrors a realistic OpenClaw project layout so the Files browser feels live
// without hitting any real API.

export type FileKind = 'folder' | 'file'

export interface FileNode {
  path: string
  name: string
  kind: FileKind
  size?: number
  mtime?: number
  ext?: string
  children?: FileNode[]
}

const now = Date.parse('2026-05-01T08:00:00Z')

function file(path: string, size: number, ext: string, mtimeOffsetSec = 0): FileNode {
  const name = path.split('/').pop() ?? path
  return { path, name, kind: 'file', size, ext, mtime: now + mtimeOffsetSec * 1000 }
}

function folder(path: string, children: FileNode[]): FileNode {
  const name = path.split('/').pop() ?? path
  return { path, name, kind: 'folder', children, mtime: now }
}

export const FIXTURE_TREE: FileNode = folder('/', [
  folder('/workspace', [
    file('/workspace/README.md', 2048, 'md', -3600),
    file('/workspace/SOUL.md', 1536, 'md', -7200),
    file('/workspace/USER.md', 980, 'md', -10800),
    folder('/workspace/memory', [
      file('/workspace/memory/2026-05-01.md', 4096, 'md', -1800),
      file('/workspace/memory/2026-04-30.md', 6500, 'md', -90000),
      file('/workspace/memory/index.json', 512, 'json', -1800),
    ]),
    folder('/workspace/skills', [
      file('/workspace/skills/weather.ts', 1200, 'ts', -86400),
      file('/workspace/skills/github.ts', 2400, 'ts', -86400),
    ]),
  ]),
  folder('/assets', [
    file('/assets/logo.png', 24576, 'png', -432000),
    file('/assets/avatar.jpg', 18432, 'jpg', -432000),
    file('/assets/intro.mp4', 5242880, 'mp4', -1000000),
  ]),
  folder('/config', [
    file('/config/app.json', 768, 'json', -7200),
    file('/config/theme.json', 420, 'json', -7200),
    file('/config/secrets.bin', 256, 'bin', -7200),
  ]),
  file('/CHANGELOG.md', 3200, 'md', -3600),
  file('/package.json', 612, 'json', -86400),
])

export const FIXTURE_CONTENT: Record<string, string> = {
  '/workspace/README.md': `# OpenClaw Workspace

Welcome 斌哥.

This is a **stub** preview of \`README.md\` rendered through \`useMarkdown\`.

- 📁 Files browser
- 📊 Perf monitor
- 🤖 Agents

\`\`\`ts
const x: number = 42
console.log(x)
\`\`\`
`,
  '/workspace/SOUL.md': `# SOUL\n\n_Be genuinely helpful, not performatively helpful._\n`,
  '/workspace/USER.md': `# USER\n\n- **Name:** 斌哥\n- **TZ:** Asia/Shanghai\n`,
  '/workspace/memory/2026-05-01.md': `# 2026-05-01\n\n- 跑了一下 Phase D3 的子任务，文件浏览器和性能监测面板都顺利。\n- 测试全绿。\n`,
  '/workspace/memory/2026-04-30.md': `# 2026-04-30\n\n- Phase C 合并完毕。\n`,
  '/workspace/memory/index.json': JSON.stringify(
    { lastSeen: '2026-05-01', count: 42, topics: ['phase-d', 'files', 'perf'] },
    null,
    2,
  ),
  '/workspace/skills/weather.ts': `export function getWeather(city: string): Promise<string> {\n  return fetch('https://wttr.in/' + city).then((r) => r.text())\n}\n`,
  '/workspace/skills/github.ts': `import { execSync } from 'node:child_process'\nexport function listIssues(repo: string): string {\n  return execSync('gh issue list -R ' + repo).toString()\n}\n`,
  '/CHANGELOG.md': `# CHANGELOG\n\n## v2 — refactor\n- Phase A scaffold\n- Phase B comms\n- Phase C chat + sidebar\n- **Phase D3** Files + Perf\n`,
  '/package.json': JSON.stringify(
    { name: 'openclaw', version: '2.0.0', private: true, workspaces: ['packages/*'] },
    null,
    2,
  ),
  '/config/app.json': JSON.stringify(
    { port: 7685, host: '127.0.0.1', logLevel: 'info', features: { files: true, perf: true } },
    null,
    2,
  ),
  '/config/theme.json': JSON.stringify({ default: 'dark', accent: '#10a37f' }, null, 2),
}

export const FIXTURE_IMAGE_PLACEHOLDER =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="200" viewBox="0 0 320 200">
      <rect width="100%" height="100%" fill="#2a2b32"/>
      <text x="50%" y="50%" font-family="sans-serif" font-size="14" fill="#8e8ea0" text-anchor="middle" dy=".3em">stub image preview</text>
    </svg>`,
  )
