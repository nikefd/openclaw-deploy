// config.js — All runtime config centralized here.
// Change the backend? Change this file + swap the backend adapter. Nothing else.

export const config = Object.freeze({
  // Backend identity (for logging / diagnostics)
  backendName: 'openclaw',

  // OpenClaw gateway (proxied by nginx at /v1 and /api)
  // If we migrate to Hermes, only the adapter changes — these URLs stay the same
  // because nginx does the routing.
  gateway: {
    chatCompletions: '/v1/chat/completions',
    sessionsHistory: '/v1/sessions',   // + /{chatId}/history
    cronJobs: '/v1/cron/jobs',
  },

  // Our own Node services
  api: {
    chats: '/api/chats',               // GET list, POST bulk-backup, DELETE one
    chatOne: '/api/chats/',            // + encodeURIComponent(id)  GET/PUT/DELETE
    chatHistory: '/api/chat/history',  // ?chatId=&agent=
    chatSend: '/api/chat/send',        // POST  (fire-and-forget proxy submit)
    copilotStream: '/api/copilot/stream', // POST  (server-authoritative streaming)
    files: {
      list: '/api/files/list',
      read: '/api/files/read',
      write: '/api/files/write',
      download: '/api/files/download',
    },
    perfLog: '/api/perf/log',
    authLogout: '/auth/logout',
  },

  // localStorage keys
  storage: {
    chats: 'oc_chats_v2',
    agent: 'oc_selected_agent',
    theme: 'oc_theme',
    model: 'oc_model',
  },

  // Workspace root on the node
  workspace: '/home/nikefd/.openclaw/workspace',

  // Cron job that does memory tidying
  memoryCronId: 'memory-tidy-daily',

  // Available models (id must match OpenClaw model id)
  models: [
    { id: 'github-copilot/claude-opus-4.7',      name: 'Claude Opus 4.7',     emoji: '🐙', icon: '🐙', cost: '10x', desc: '最强模型，深度思考' },
    { id: 'github-copilot/claude-opus-4.6-fast', name: 'Opus 4.6 (Fast)',     emoji: '⚡', icon: '⚡', cost: '5x',  desc: '平衡速度和能力' },
  ],

  // Model → agentId override (for gateway routing).
  // 'main' means "no agent override", just use the model directly.
  modelToAgent: {
    'github-copilot/claude-opus-4.7': 'opus',
    'github-copilot/claude-opus-4.6-fast': 'opus-fast',
  },
});

// Convenience helpers — keeps call sites from constructing paths by hand.
export const urls = {
  chatOne: (id) => config.api.chatOne + encodeURIComponent(id),
  chatHistory: (chatId, agent) =>
    `${config.api.chatHistory}?chatId=${encodeURIComponent(chatId)}&agent=${encodeURIComponent(agent)}`,
  filesList: (path) => path ? `${config.api.files.list}?path=${encodeURIComponent(path)}` : config.api.files.list,
  filesRead: (path) => `${config.api.files.read}?path=${encodeURIComponent(path)}`,
  filesDownload: (path) => `${config.api.files.download}?path=${encodeURIComponent(path)}`,
  sessionHistory: (chatId, limit = 4) =>
    `${config.gateway.sessionsHistory}/${encodeURIComponent(chatId)}/history?limit=${limit}`,
  cronJob: (id) => `${config.gateway.cronJobs}/${encodeURIComponent(id)}`,
};

// Resolve model → wire model name used with OpenClaw (e.g. "openclaw/opus").
// Other backends (Hermes) can ignore this and implement their own resolution.
export function resolveWireModel(modelId) {
  const agent = config.modelToAgent[modelId];
  return agent ? `openclaw/${agent}` : 'openclaw';
}
