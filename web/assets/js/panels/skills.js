// panels/skills.js —— Skills 面板（扫描本地 SKILL.md 列表、搜索、筛选、详情）
// 对外暴露（供 HTML inline onclick 使用）：
//   setSkillFilter / filterSkills / openSkill / closeSkillDetail

const SK_ICONS = {
  discord: '💬', github: '🐙', 'gh-issues': '🐛', weather: '🌤', tmux: '🖥',
  'video-frames': '🎬', healthcheck: '🛡', 'skill-creator': '✨',
  'node-connect': '🔗', 'coding-agent': '🤖', himalaya: '📧', slack: '💼',
  'spotify-player': '🎵', 'voice-call': '📞', sag: '🔊', camsnap: '📷',
  notion: '📓', obsidian: '💎', trello: '📋', '1password': '🔐', gog: '📬',
  xurl: '🐦', summarize: '📝', 'nano-pdf': '📄', oracle: '🔮',
  sonoscli: '🔈', openhue: '💡', peekaboo: '👀', gemini: '♊',
  clawhub: '🦞', 'web-dev-rules': '🚧', 'mermaid-fix': '🧜', 'memory-ops': '🧠',
};
const ACTIVE_SKILLS = new Set([
  'discord', 'gh-issues', 'github', 'healthcheck', 'skill-creator',
  'node-connect', 'tmux', 'video-frames', 'weather',
]);

let skillsData = [];
let skillFilter = 'all';
let skillsLoaded = false;

function escH(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export async function loadSkillsPanel() {
  if (skillsLoaded) return;
  skillsLoaded = true;
  const builtinPath = '/home/nikefd/.npm-global/lib/node_modules/openclaw/skills';
  const customPath = '/home/nikefd/.openclaw/workspace/skills';
  async function scanDir(basePath, isBuiltin) {
    try {
      const r = await fetch('/api/files/list?path=' + encodeURIComponent(basePath));
      const d = await r.json();
      if (!d.entries) return;
      for (const e of d.entries) {
        if (e.type !== 'directory' && e.type !== 'dir') continue;
        let desc = '';
        try {
          const sr = await fetch('/api/files/read?path=' + encodeURIComponent(e.path + '/SKILL.md'));
          const sd = await sr.json();
          if (sd.content) {
            const m = sd.content.match(/description:\s*["']?(.+?)["']?\s*$/m)
                   || sd.content.match(/^#\s*(.+)/m);
            if (m) desc = m[1].substring(0, 150);
          }
        } catch (x) {}
        skillsData.push({
          name: e.name,
          description: desc || '暂无描述',
          active: isBuiltin ? ACTIVE_SKILLS.has(e.name) : true,
          builtin: isBuiltin,
          icon: SK_ICONS[e.name] || '🧩',
        });
      }
    } catch (e) {}
  }
  await Promise.all([scanDir(builtinPath, true), scanDir(customPath, false)]);
  skillsData.sort((a, b) =>
    (b.active - a.active) || (a.builtin - b.builtin) || a.name.localeCompare(b.name));
  renderSkillsGrid();
}

export function setSkillFilter(f) {
  skillFilter = f;
  document.querySelectorAll('#panel-skills .skill-filter')
    .forEach(b => b.classList.toggle('active', b.dataset.filter === f));
  renderSkillsGrid();
}

export function filterSkills() { renderSkillsGrid(); }

function getVisibleSkills() {
  const q = (document.getElementById('skillSearch')?.value || '').toLowerCase();
  return skillsData.filter(s => {
    if (q && !s.name.includes(q) && !s.description.toLowerCase().includes(q)) return false;
    if (skillFilter === 'active') return s.active;
    if (skillFilter === 'builtin') return s.builtin;
    if (skillFilter === 'custom') return !s.builtin;
    return true;
  });
}

function renderSkillsGrid() {
  const grid = document.getElementById('skillsGrid');
  if (!grid) return;
  const vis = getVisibleSkills();
  const ct = document.getElementById('skillsCounts');
  if (ct) {
    ct.textContent = skillsData.length + ' 个技能 · '
      + skillsData.filter(s => s.active).length + ' 已启用 · '
      + skillsData.filter(s => !s.builtin).length + ' 自定义';
  }
  if (!vis.length) {
    grid.innerHTML = '<div style="grid-column:1/-1;padding:40px;text-align:center;color:var(--text-sec)">🔍 没有匹配的技能</div>';
    return;
  }
  grid.innerHTML = vis.map(s =>
    '<div class="skill-card" onclick="openSkill(\'' + s.name + '\')">'
    + '<div class="sk-icon">' + s.icon + '</div>'
    + '<div class="sk-name">' + escH(s.name) + '</div>'
    + '<div class="sk-desc">' + escH(s.description) + '</div>'
    + '<div class="sk-tags">'
    + (s.active ? '<span class="sk-tag on">✅ 已启用</span>' : '<span class="sk-tag">未启用</span>')
    + (s.builtin ? '<span class="sk-tag">📦 内置</span>' : '<span class="sk-tag custom">🛠 自定义</span>')
    + '</div></div>'
  ).join('');
}

export async function openSkill(name) {
  const detail = document.getElementById('skillDetail');
  detail.style.display = 'flex';
  document.getElementById('skillDetailTitle').textContent = name;
  const body = document.getElementById('skillDetailBody');
  body.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-sec)">🔄 加载中...</div>';
  const paths = [
    '/home/nikefd/.openclaw/workspace/skills/' + name + '/SKILL.md',
    '/home/nikefd/.npm-global/lib/node_modules/openclaw/skills/' + name + '/SKILL.md',
  ];
  let content = '';
  for (const p of paths) {
    try {
      const r = await fetch('/api/files/read?path=' + encodeURIComponent(p));
      const d = await r.json();
      if (d.content) { content = d.content; break; }
    } catch (e) {}
  }
  if (!content) {
    body.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-sec)">📄 SKILL.md 未找到</div>';
    return;
  }
  let h = escH(content);
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, (m, l, c) => '<pre><code>' + c + '</code></pre>');
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/^- (.+)$/gm, '<li>$1</li>');
  h = h.replace(/\n\n/g, '<br><br>');
  body.innerHTML = h;
}

export function closeSkillDetail() {
  document.getElementById('skillDetail').style.display = 'none';
}

// NOTE: the 'skills' tab lazy-load is already wired inside the legacy tab
// loop in index.html (`if(tab.dataset.tab==='skills'&&!skillsLoaded) loadSkillsPanel()`).
// That call site resolves `loadSkillsPanel` from window — main.js attaches it.
// No separate wire hook needed here.
