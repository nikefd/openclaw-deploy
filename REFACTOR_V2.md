# REFACTOR_V2 — 前端 TS 化 + 实时通信治理

> 起草：2026-05-07 17:21 CST
> 起草人：狗蛋（受斌哥要求）
> 参考：[EKKOLearnAI/hermes-web-ui](https://github.com/EKKOLearnAI/hermes-web-ui)（Vue 3 + TS + Pinia + Vite + Socket.IO）
> 现状基线：`index.html` 2152 行、`agents.html` 2585 行、`web/src/` 4153 行 vanilla JS（IIFE + `window.__oc` 全局桥）

---

## 0. 这次为什么要重启重构

REFACTOR_v1 已经把 `index.html` 从 3170→2152 行，`web/src/` 抽出 4153 行模块。但**继续往下抽收益越来越小**，因为：

1. **HTML / CSS / JS 仍在同一个文件耦合**。每次改 chat 都要在 2152 行 HTML 里翻 `<script>` 内联块。
2. **没有类型系统**。`send()` 那种 7 层嵌套巨型函数，纯 JS 改一次翻一次车（24h 内 3 连击 bug 就是案例）。
3. **没有组件边界**。模块抽出来只是函数集合，模板还是字符串拼接 + `innerHTML`，每次都要手动加 escape。
4. **🔥 真正的瓶颈在通信层**：现在 chat 走 `/api/copilot/stream` SSE，前端断线就丢消息，靠 4 套补丁顶着（`streamRecovery` 看门狗 / `streamPollLoop` 移动端轮询 / `pollOne` 兜底 / `tryRecover` 已删但同款 bug 复发过 2 次）。这是架构问题，不是补丁能根治的。

参考 hermes 的设计：**Socket.IO + room（key=session_id）+ 服务端 EventSource 上游 + DB 落盘**。客户端断了上游照推，重连 `emit('resume', sid)` 重新入房间，DB 是真相，前端只是订阅者。轮询直接消失。

---

## 1. 目标架构（终态）

```
zhangyangbin-web/                    # 新仓库 or openclaw-deploy/web-v2/
├── packages/
│   ├── client/                      # Vue 3 + TS + Vite
│   │   ├── src/
│   │   │   ├── main.ts
│   │   │   ├── App.vue
│   │   │   ├── router/
│   │   │   ├── stores/              # Pinia
│   │   │   │   ├── chat.ts
│   │   │   │   ├── session.ts
│   │   │   │   ├── memory.ts
│   │   │   │   ├── nodes.ts
│   │   │   │   ├── tasks.ts
│   │   │   │   └── auth.ts
│   │   │   ├── api/
│   │   │   │   ├── client.ts        # fetch wrapper
│   │   │   │   ├── chat-socket.ts   # ⭐ Socket.IO 客户端
│   │   │   │   ├── chats.ts         # REST: list/get/save/delete
│   │   │   │   ├── memory.ts
│   │   │   │   ├── files.ts
│   │   │   │   ├── tasks.ts
│   │   │   │   └── perf.ts
│   │   │   ├── composables/
│   │   │   │   ├── useChatStream.ts # ⭐ 订阅 + 重连 + resume
│   │   │   │   ├── useTypewriter.ts
│   │   │   │   ├── useMarkdown.ts
│   │   │   │   ├── useTTS.ts
│   │   │   │   └── useMentions.ts
│   │   │   ├── components/
│   │   │   │   ├── chat/
│   │   │   │   │   ├── ChatView.vue
│   │   │   │   │   ├── MessageList.vue
│   │   │   │   │   ├── MessageBubble.vue
│   │   │   │   │   ├── MessageInput.vue
│   │   │   │   │   ├── ModelDropdown.vue
│   │   │   │   │   └── MentionPopup.vue
│   │   │   │   ├── sidebar/
│   │   │   │   │   ├── ChatSidebar.vue
│   │   │   │   │   ├── MemoryPanel.vue
│   │   │   │   │   ├── SkillsPanel.vue
│   │   │   │   │   └── NodesPanel.vue
│   │   │   │   ├── files/
│   │   │   │   ├── tasks/
│   │   │   │   └── layout/
│   │   │   ├── views/
│   │   │   │   ├── ChatView.vue
│   │   │   │   ├── AgentsView.vue
│   │   │   │   ├── TasksView.vue
│   │   │   │   ├── ArchitectureView.vue
│   │   │   │   ├── PerfView.vue
│   │   │   │   └── LoginView.vue
│   │   │   ├── styles/
│   │   │   │   ├── variables.scss
│   │   │   │   ├── global.scss
│   │   │   │   └── theme.ts
│   │   │   ├── types/               # 共享 type
│   │   │   │   ├── chat.ts
│   │   │   │   ├── memory.ts
│   │   │   │   └── events.ts        # ⭐ Socket.IO event 协议
│   │   │   └── utils/
│   │   ├── public/
│   │   ├── index.html               # 30 行骨架，仅挂载点
│   │   ├── tsconfig.json
│   │   └── vite.config.ts
│   ├── server/                      # 替代当前 file-api-server.js / agents-api.js / auth-server.js
│   │   ├── src/
│   │   │   ├── index.ts             # express + socket.io 启动
│   │   │   ├── routes/
│   │   │   │   ├── chats.ts         # REST CRUD
│   │   │   │   ├── memory.ts
│   │   │   │   ├── files.ts
│   │   │   │   ├── tasks.ts
│   │   │   │   ├── auth.ts
│   │   │   │   └── perf.ts
│   │   │   ├── services/
│   │   │   │   ├── chat-stream.ts   # ⭐ Socket.IO /chat-run namespace
│   │   │   │   ├── upstream/        # OpenClaw / Copilot bridge
│   │   │   │   │   ├── copilot-bridge.ts
│   │   │   │   │   └── openclaw-bridge.ts
│   │   │   │   └── chat-repo.ts     # 现有 lib/chatRepo.js TS 化
│   │   │   ├── lib/
│   │   │   │   ├── logger.ts
│   │   │   │   └── auth-mw.ts
│   │   │   └── types/               # ⭐ 与 client 共享 events.ts
│   │   └── tsconfig.json
│   └── shared/                      # client/server 共享 type & schema
│       ├── events.ts                # SocketEvents、消息协议
│       ├── chat.ts
│       └── api-schema.ts            # zod schema, 双端 runtime 校验
├── package.json                     # workspaces
├── tsconfig.base.json
├── vitest.config.ts
└── docker-compose.yml (可选)
```

**关键决策**：
- **Vue 3 + Composition API + TS**（对标 hermes-web-ui，比 React 更轻；斌哥之前没强烈倾向 React，hermes 也是 Vue）
- **Vite** 开发热更（取代当前 ttyd/手刷）
- **Pinia** 状态管理（chat 按 sessionId 切片）
- **Socket.IO**（不是 raw WebSocket，因为要 fallback + room + reconnect）
- **TypeScript strict**（types 双端共享 via `packages/shared`）
- **Vitest** 取代当前 `node --test`（vitest 兼容现有 .mjs，逐步迁）
- **保留**现在的 finance-api / usage-api / perf-api / gateway 不动；只重构 chat / agents / files 这一坨前端 + file-api-server.js

---

## 2. 通信层重设计 ⭐ 这是核心

### 现状（病灶）

```
[browser] ─POST /api/copilot/stream──▶ [file-api 7682] ─stream──▶ [Copilot upstream]
            │                              │
            │  断线 = 流断 = 消息丢          │  实时落盘 chats/<id>.json
            ▼                              ▼
       streamRecovery 看门狗           save() debounce 500ms
       streamPollLoop 轮询             (前端断了仍写完上游)
       pollOne signature check
       tryRecover (已删)
```

补丁层数 = bug 数 = 凌晨告急次数。

### 目标（hermes 范式）

```
[browser] ──io('/chat-run')──▶ [server socket.io] ─────▶ [upstream SSE]
            │ emit('start', {sid, input})       │
            │ emit('resume', sid) on reconnect  │ writes ──▶ chat-repo (DB/file)
            ▼                                   │ broadcasts ──▶ room(sid)
       订阅 message.delta                       │
       订阅 run.completed                       ▼
       断线 = io.disconnect → 重连自动 resume  其它 tab/设备同 sid 也收到
```

**核心保证**：
1. **服务端 = 真相源**。客户端只是 room 订阅者。
2. **断线不丢**。客户端 disconnect 不影响上游；reconnect emit `resume` 重新入 room；如果 run 已完成，直接拉最新 chat 状态。
3. **多设备同步**。同一 chatId 在手机 + 电脑同时打开，两边都收到 delta（room 广播）。
4. **轮询消失**。`streamPollLoop` / `streamRecovery` / `pollOne` 全删。
5. **离线追赶**。每条 delta 带 `seq` 序号，client 记录 `lastSeq`，resume 时 server 把 `seq > lastSeq` 的 events replay 一遍。

### Socket.IO 事件协议（写在 `packages/shared/events.ts`）

```ts
// client → server
interface ClientToServer {
  start: (req: StartRunRequest) => void
  resume: (sessionId: string, lastSeq?: number) => void
  abort: (sessionId: string) => void
}

// server → client
interface ServerToClient {
  'run.queued':     (e: { sid: string; runId: string; seq: number }) => void
  'run.started':    (e: { sid: string; runId: string; seq: number }) => void
  'message.delta':  (e: { sid: string; runId: string; delta: string; seq: number }) => void
  'tool.started':   (e: { sid: string; tool: string; seq: number }) => void
  'tool.completed': (e: { sid: string; tool: string; preview?: string; seq: number }) => void
  'run.completed':  (e: { sid: string; runId: string; output: string; usage: Usage; seq: number }) => void
  'run.failed':     (e: { sid: string; runId: string; error: string; seq: number }) => void
}
```

服务端持久化每个 run 的事件流到 `chats/<id>.json` 的 `events[]` 数组（截断保留最后 N 条），resume 时从 `events.filter(e => e.seq > lastSeq)` replay。

---

## 3. 阶段拆解（**所有 phase 都通过 sub-agent 执行**，主会话只验收）

> 全部走 git branch `refactor-v2/<phase-name>`，每 phase 独立 PR + smoke 测试。
> **绝不直接覆盖 `web/index.html`**，新代码全在 `packages/client/`，老页面继续服役直到 v2 完整可用。

### Phase A — 脚手架（半天，sub-agent）
- [ ] 在 `openclaw-deploy/` 下新建 `packages/{client,server,shared}` workspace
- [ ] 根 `package.json` 加 `workspaces`、`tsconfig.base.json`、`.eslintrc`、`.prettierrc`
- [ ] `packages/client`：vite + vue-tsc + pinia + vue-router + socket.io-client + sass
- [ ] `packages/server`：express + socket.io + ts-node + vitest
- [ ] `packages/shared`：zod + 双端 type
- [ ] CI 跑通 `npm run build` + `npm run test`
- [ ] **不动**任何现有文件

### Phase B — 通信骨架（核心，sub-agent）
- [ ] `packages/server` 起 socket.io，监听 8000 端口（dev）
- [ ] 实现 `/chat-run` namespace：`start` / `resume` / `abort` 三个事件
- [ ] 上游桥接：`copilot-bridge.ts` 把现有 `file-api-server.js` 的 `/api/copilot/stream` 逻辑搬过来，但暴露给 socket.io
- [ ] `events[]` seq 持久化到 `~/.openclaw/chats/<id>.json`（兼容旧格式）
- [ ] `packages/client/composables/useChatStream.ts`：订阅、断线重连、resume、`lastSeq` 追赶
- [ ] **写测试**：模拟客户端断 5 秒，server 继续推 → 重连后收到全部 delta（用 vitest）
- [ ] dev 环境通过 nginx 加一条 `/socket.io/` proxy 到 8000

### Phase C — 复刻 chat UI（最大块，sub-agent x N）
- [ ] `App.vue` + router + 主题（dark/light，从现有 CSS 变量搬）
- [ ] `ChatView.vue` + `MessageList.vue` + `MessageBubble.vue` + `MessageInput.vue`
- [ ] `ChatSidebar.vue`（chat list, group, search）
- [ ] `ModelDropdown.vue` + `MentionPopup.vue`
- [ ] markdown 渲染走 `marked` + `highlight.js`（v3 同款）
- [ ] **typewriter 动画**用 composable，不写到组件里（避免 send() 巨型化重演）
- [ ] 走猫咪 typing indicator 复刻
- [ ] 端到端 demo：`/v2/` 路径下能完整跑一轮 chat
- [ ] nginx 加 location `/v2/` → vite preview build 静态文件

### Phase D — 旁支页面（并行 sub-agent）
- [ ] `AgentsView.vue`（agents.html → Vue）
- [ ] `TasksView.vue`（tasks dashboard）
- [ ] `MemoryPanel.vue`（含"手动整理"按钮）
- [ ] `FilesView.vue`（file browser）
- [ ] `PerfView.vue`（perf.html）
- [ ] `ArchitectureView.vue`（architecture.html）

### Phase E — 后端整合（sub-agent）
- [ ] `packages/server` 把 `file-api-server.js` 全部 endpoint TS 化迁过来
- [ ] `chat-repo.ts` 替换现有 `lib/chatRepo.js`，添加事件流持久化
- [ ] 旧 `file-api-server.js` 保留为备用，新 server 跑在 8001 端口
- [ ] 灰度：nginx 把 `/api/files/` `/api/chats/` `/socket.io/` 切到新 server，其它继续旧的
- [ ] 跑两周，老 server 退役

### Phase F — 切换 + 清退（sub-agent）
- [ ] `/v2/` 升级为 `/`，老 `/var/www/chat/index.html` 移到 `/legacy/`
- [ ] 全量 smoke 测试（chat / 断线重连 / 多设备 / agents / files / tasks）
- [ ] 跑一周观察后删除 legacy
- [ ] `web/src/` 整个目录归档到 `archive/web-v1-src/`
- [ ] 老 service：`agents-api.js` / `usage-api.js` / `perf-api.js` 保留不动（不在重构范围）

---

## 4. 时间预估

| Phase | 内容 | 工时 | 谁干 |
|-------|------|------|------|
| A | 脚手架 | 0.5d | sub-agent |
| B | 通信骨架 + 测试 | 2d | sub-agent（关键） |
| C | chat UI 复刻 | 3-4d | 2 个 sub-agent 并行 |
| D | 旁支页面 | 2d | sub-agent 并行 |
| E | 后端整合 | 1.5d | sub-agent |
| F | 切换 + 清退 | 1d + 观察期 | sub-agent + 斌哥拍板 |
| **合计** | **≈10 工作日**（不含观察期） |

---

## 5. 风险与对策

| 风险 | 对策 |
|------|------|
| Vue / TS 学习曲线 | 严格对标 hermes-web-ui 的目录结构，复制粘贴改造比白手起家快 5x |
| Socket.IO + nginx 配置坑（断流、超时） | nginx `proxy_read_timeout 3600s; proxy_buffering off; Upgrade/Connection 头` |
| 旧 `index.html` 还在演化（金融/攀岩面板还在改） | v2 期间老页面**冻结新功能**，只接 hot-fix |
| Phase C 失控（chat 业务太多） | 单 phase 不超过 3 天，超时切出独立 phase |
| 通信层切换炸产 | `/v2/` 路径灰度 → 自己用 1 周 → 才切 `/` |
| 双端 type 漂移 | `packages/shared` 唯一来源；CI 强制 `tsc --noEmit` |

---

## 6. 立即行动（要斌哥拍板的事）

1. **要不要新仓库**？建议**留在 `openclaw-deploy/`** 同仓 + `packages/` workspace（部署脚本不用大改）。
2. **Vue 3 vs React**？建议 **Vue 3**（对齐 hermes，社区生态够用，Composition API 比 React hooks 更可控）。
3. **Socket.IO vs raw WS / SSE-with-resume**？建议 **Socket.IO**（room + auto-reconnect + 透明降级，hermes 已验证）。
4. **要不要保留 jQuery 风格 `window.__oc` 全局桥**？**不要**。v2 一刀切 ESM + Pinia。
5. **测试栈** Vitest + Playwright（端到端）？建议是。

确认这 5 点后，我就可以开始派 sub-agent 跑 Phase A。

---

## 7. 不在本次重构范围内的东西（防止 scope creep）

- ❌ 金融 Agent 的 Python 代码（finance-api / stock_picker.py 等）
- ❌ Gateway / OpenClaw 内核
- ❌ usage-api / perf-api / agents-api 三个旁支 service（只迁主 file-api）
- ❌ nginx 全局重写（只加新 location）
- ❌ ttyd 终端、auth-server 登录流程（先复用，后期再说）

---

_本计划是活文档。每完成一个 phase 在 §3 打勾、commit hash 记下来。_
