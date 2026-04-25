# REFACTOR — 聊天系统 Clean Architecture 重构

> 起始 commit: `bb54ef8`（chat: server-authoritative chat persistence）
> 分支: `refactor-phase-0` → 后续每个 phase 一个分支
> 负责人: 狗蛋 🐶 + 斌哥

## 总目标

1. **解耦 OpenClaw**：后端可切换（OpenClaw → Hermes 或其它），前端通过 `ChatBackend` interface 对接
2. **Clean Architecture 分层**：UI / Application / Domain / Infrastructure 边界清晰，依赖只向内
3. **Agents 独立**：finance / climbing / interview 等每个 agent 独立模块，可单独迭代 / 下线 / 迁移
4. **零打包器**：原生 ES modules，nginx 静态托管即可

## 目标目录结构

```
openclaw-deploy/
├── web/
│   ├── index.html           # 聊天主入口（瘦身到 <500 行）
│   ├── agents.html          # agents 面板（同样瘦身）
│   ├── assets/
│   │   └── css/             # 抽离后的 CSS（base / chat / typing / sidebar）
│   └── src/
│       ├── ui/              # View 组件：Sidebar / MessageList / Composer / CatTyping
│       ├── app/             # Use cases：chatFlow / agentRouter / heartbeat
│       ├── domain/          # 纯数据模型：Chat / Message / Agent / User
│       └── infra/
│           ├── config.js    # 所有 URL / Agent ID / 常量集中
│           ├── backend/     # ChatBackend 接口 + 实现（openclaw / copilot / hermes...）
│           └── storage/     # localStorage + server sync 封装
├── services/                 # 后端 Node 服务统一归位
│   ├── file/    (7682)
│   ├── auth/    (7683)
│   ├── finance/ (7684)
│   ├── agents/  (7685)
│   ├── usage/   (7686)
│   └── perf/    (7687)
├── lib/                      # 跨服务共享：http / storage / logger
└── agents-runtime/           # 独立 agent 包（finance / climbing / interview...）
```

## Phase 计划

| Phase | 任务 | 风险 | 预估 | 状态 |
|-------|------|------|------|------|
| 0 | 建分支 + 骨架目录 + 本文档 | ⬇️ | 10m | ✅ `48e13bd` |
| 1 | 抽 CSS 到 assets/css/ | ⬇️ | 30m | ✅ `c2711fa` |
| 2 | infra 层：config / backend / storage | ⬇️⬇️ | 1h | ✅ `76d01bb` |
| 3 | 接线 infra + 抽 domain | ⬇️⬇️ | 3h | ✅ 3a/3.1–3.5 |
| 4 | UI 组件化 | ⬇️⬇️ | 2h | ⬜ |
| 5 | 后端 services/ 重组 | ⬇️ | 1h | ⬜ |
| 6 | agents 抽成独立包 | ⬇️⬇️ | 2h | ⬜ |

## 原则

- **每个 phase 独立可部署、可回滚**：完成后 commit + 斌哥亲测 + 合并到 main
- **老文件原地保留**直到新版本验证完全等价，再删
- **不改行为，只改结构**：重构期间不新增功能、不修无关 bug
- **任何一步翻车**：`git reset --hard bb54ef8` 回到起点

## 进度日志

### 2026-04-24 Phase 0 — `48e13bd`
- 分支 `refactor-phase-0` 创建
- 骨架目录搭建：`web/src/{ui,app,domain,infra/{backend,storage}}` / `services/{file,auth,agents,finance,usage,perf}/lib` / `lib/{http,storage,logger}`
- REFACTOR.md 创建（本文档）

### 2026-04-25 Phase 1 — `c2711fa`
- `index.html` 内联 `<style>` (1041 行) 原样抽到 `web/assets/css/app.css`
- `<style>...</style>` 替换为 `<link rel="stylesheet" href="/assets/css/app.css">`
- `index.html` 从 3170 → 2128 行 (-33%)
- 已同步到 `/var/www/chat/`，线上备份：`index.html.bak-phase1-20260425-*`
- **待斌哥实测确认视觉零变化 → 合并 main**

### 2026-04-25 Phase 2 — `76d01bb` + 修正 `02783d6`
- infra 层建成：`config` / `backend/{ChatBackend, OpenClawBackend, backendFactory}` / `storage/{localStore, chatStore}` / `telemetry` / `index`
- Hermes 迁移成本：新写一个 `HermesBackend.js` + 改 `backendFactory.js` 一行
- ❗ **踩坑**：死过一次。我加的 `<script type="module" src="/src/infra/index.js">` 触发無限重刷 — `location /` 有 `try_files ... /index.html` fallback，module 请求任何环节 miss 都会拿回 index.html，HTML 被当 module 或被重渲染，启动 IIFE 再 fetch `/api/chats` → 死循环。
- ✅ 修正：infra 代码留在仓库，但 `index.html` 不加 script tag。Phase 3 直接在开始接线时用更安全的方式（独立 location / 打包成单文件）。
- 已同步 `/var/www/chat/`，备份：`index.html.bak-phase2-*`

### 2026-04-25 Phase 3 — 接线 infra + 抽 domain
分 5 个子步逐个验证，每步独立 commit：

- **3a `5089d8b`**: nginx 加 `/src/` 和 `/assets/` 独立 location，不带 try_files fallback。避开 Phase 2 踩过的重刷雷 — module script 现在能安全加载。
- **3.1 `0c45eaa`**: `perfLog` 迁到 `infra/telemetry`。最小面积验证路径。
- **3.2 `d1986aa`**: model / theme / agent prefs 迁到 `infra/prefs`，`localStore` 加 `setChatsForNode` + 自动 `stripImages`。
- **3.3 `c9e2370`**: 9 个 chats CRUD fetch 调用点迁到 `infra/backend`。新增 `getChat / saveChatBeacon / loadChatsSince / clearAllChats`。
- **3.4 `8acf9ba`**: SSE 流式主路径 — 加 `buildStreamRequest` 抽象，UI 仍自己 `reader.read()` 保留 perf/visibility 逻辑。`resolveWireModel` 改为幂等。
- **3.5 `_THIS_`**: domain 层 — `web/src/domain/chat.js` 提供 `mergeChats / createChat / findChat / escapeHtml / genChatId` 等纯函数。`window.__oc.domain.chat.*` 可调，inline 版本作 fallback。

**迁移模式**（贯穿所有子步）：`window.__oc?.X?.method?.() ?? 原始实现` — module 未加载时行为与重构前等同，0 风险。

**代码布局**（Phase 3 后）：
```
web/src/
  domain/chat.js              # 纯函数，能单独单测
  infra/
    config.js                  # 所有 URL、存储 key、模型表
    backend/{ChatBackend,OpenClawBackend,backendFactory}.js
    storage/{localStore,chatStore}.js
    telemetry.js
    index.js                   # 唯一公开入口 → window.__oc
```

**Hermes 迁移表面积**（Phase 3 后）：新写 `HermesBackend.js`（实现 9 个接口方法）+ 改 `backendFactory.js` 一行。UI 代码零修改。

