// panels/experts.js —— 帮帮团（专家并行分析）
// 对外暴露（供 HTML inline onclick 使用）：
//   toggleExpertPanel / selectExpertTeam / queryExperts / cancelExpertRequests
// 依赖：window.API / window.TOKEN (set by main.js from config.js)

const $ = (id) => document.getElementById(id);

const EXPERT_TEAMS = [
  { id: 'code-review', name: '代码审查', icon: '🔍', experts: [
    { id: 'arch',     name: '架构师',   icon: '🏗️', prompt: '你是一位资深软件架构师。从架构设计、可扩展性、设计模式角度分析用户的问题。简洁直接，给出具体建议。用中文回答。' },
    { id: 'security', name: '安全专家', icon: '🔒', prompt: '你是一位网络安全专家。从安全漏洞、最佳安全实践角度分析用户的问题。指出潜在风险并给出修复建议。用中文回答。' },
    { id: 'perf',     name: '性能专家', icon: '⚡', prompt: '你是一位性能优化专家。从性能瓶颈、内存使用、算法复杂度角度分析。给出具体的优化建议和预期改进。用中文回答。' },
  ]},
  { id: 'writing', name: '写作', icon: '✍️', experts: [
    { id: 'editor',      name: '编辑',     icon: '📝', prompt: '你是一位资深文字编辑。从文章结构、逻辑流畅度、表达精准度角度给出修改建议。用中文回答。' },
    { id: 'copywriter',  name: '文案',     icon: '💡', prompt: '你是一位创意文案。从吸引力、传播性、情感共鸣角度给出建议，提供替代方案。用中文回答。' },
    { id: 'seo',         name: 'SEO专家',  icon: '📈', prompt: '你是一位SEO和内容营销专家。从搜索优化、关键词、可读性角度给出建议。用中文回答。' },
  ]},
  { id: 'product', name: '产品', icon: '📦', experts: [
    { id: 'pm',   name: '产品经理',   icon: '📋', prompt: '你是一位资深产品经理。从用户需求、产品逻辑、优先级角度分析问题，给出可行方案。用中文回答。' },
    { id: 'ux',   name: 'UX设计师',   icon: '🎨', prompt: '你是一位UX设计师。从用户体验、交互设计、可用性角度给出建议。用中文回答。' },
    { id: 'data', name: '数据分析师', icon: '📊', prompt: '你是一位数据分析师。从数据驱动决策、指标设计、A/B测试角度给出建议。用中文回答。' },
  ]},
  { id: 'debate', name: '辩论', icon: '⚖️', experts: [
    { id: 'pro',   name: '正方', icon: '👍', prompt: '你扮演辩论正方。为用户的观点/方案找到最强有力的支持论据，从积极角度分析。用中文回答。' },
    { id: 'con',   name: '反方', icon: '👎', prompt: '你扮演辩论反方。找出用户观点/方案的潜在问题和反对理由，扮演魔鬼代言人。用中文回答。' },
    { id: 'judge', name: '裁判', icon: '⚖️', prompt: '你是中立的裁判。综合正反两方观点，给出平衡的总结和你的判断。用中文回答。' },
  ]},
];

let expertPanelOpen = false;
let selectedTeam = null;
let expertAborts = [];

export function toggleExpertPanel() {
  expertPanelOpen = !expertPanelOpen;
  $('expertPanel').classList.toggle('open', expertPanelOpen);
  $('expertToggle').classList.toggle('active', expertPanelOpen);
  if (expertPanelOpen && !selectedTeam) renderExpertTeams();
}

function renderExpertTeams() {
  $('expertTeams').innerHTML = EXPERT_TEAMS.map(t =>
    `<button class="expert-team-chip ${selectedTeam === t.id ? 'active' : ''}" onclick="selectExpertTeam('${t.id}')">${t.icon} ${t.name}</button>`
  ).join('');
}

export function selectExpertTeam(teamId) {
  selectedTeam = teamId;
  renderExpertTeams();
  const team = EXPERT_TEAMS.find(t => t.id === teamId);
  if (!team) return;
  $('expertBody').innerHTML = `<div class="expert-empty"><div class="expert-empty-icon">${team.icon}</div><div><strong>${team.name}</strong> 团队已就绪</div><div style="margin-top:8px">${team.experts.map(e => `<span style="margin:0 4px">${e.icon} ${e.name}</span>`).join('')}</div><div style="margin-top:12px;font-size:12px">发送消息后，专家会同时分析</div></div>`;
}

export function cancelExpertRequests() {
  expertAborts.forEach(a => a.abort());
  expertAborts = [];
}

export async function queryExperts(userMessage, chatHistory) {
  if (!expertPanelOpen || !selectedTeam) return;
  const team = EXPERT_TEAMS.find(t => t.id === selectedTeam);
  if (!team) return;

  cancelExpertRequests();

  // Render placeholder cards
  $('expertBody').innerHTML = team.experts.map(e =>
    `<div class="expert-card thinking" id="expert-${e.id}"><div class="expert-role"><span class="role-icon">${e.icon}</span>${e.name}</div><div class="expert-content streaming">思考中...</div></div>`
  ).join('');

  // Fire parallel requests
  team.experts.forEach(async (expert) => {
    const abort = new AbortController();
    expertAborts.push(abort);
    const card = document.getElementById('expert-' + expert.id);
    if (!card) return;
    const contentEl = card.querySelector('.expert-content');

    try {
      const msgs = [
        { role: 'system', content: expert.prompt + '\n\n请简洁回答，控制在200字以内。' },
        ...chatHistory.slice(-6).map(m => ({ role: m.role, content: m.content })),
        { role: 'user', content: userMessage },
      ];

      const res = await fetch(window.API, {
        method: 'POST',
        signal: abort.signal,
        headers: { 'Authorization': `Bearer ${window.TOKEN}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'openclaw', stream: true, messages: msgs }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);

      card.classList.remove('thinking');
      const reader = res.body.getReader(), decoder = new TextDecoder();
      let full = '', buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') break;
          try {
            const delta = JSON.parse(data).choices?.[0]?.delta?.content;
            if (delta) { full += delta; contentEl.textContent = full; }
          } catch {}
        }
      }
      if (!full) contentEl.textContent = '（无回复）';
      contentEl.classList.remove('streaming');
    } catch (e) {
      card.classList.remove('thinking');
      contentEl.classList.remove('streaming');
      if (e.name !== 'AbortError') {
        contentEl.textContent = '❌ ' + e.message;
        contentEl.style.color = 'var(--danger)';
      }
    }
  });
}

// Wire the toggle button on DOM ready.
export function wireExpertToggle() {
  const btn = $('expertToggle');
  if (btn) btn.addEventListener('click', toggleExpertPanel);
}
