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
| 0 | 建分支 + 骨架目录 + 本文档 | ⬇️ | 10m | 🟢 进行中 |
| 1 | 抽 CSS 到 assets/css/ | ⬇️ | 30m | ⬜ |
| 2 | infra 层：config / backend / storage | ⬇️⬇️ | 1h | ⬜ |
| 3 | domain + application 层 | ⬇️⬇️ | 2h | ⬜ |
| 4 | UI 组件化 | ⬇️⬇️ | 2h | ⬜ |
| 5 | 后端 services/ 重组 | ⬇️ | 1h | ⬜ |
| 6 | agents 抽成独立包 | ⬇️⬇️ | 2h | ⬜ |

## 原则

- **每个 phase 独立可部署、可回滚**：完成后 commit + 斌哥亲测 + 合并到 main
- **老文件原地保留**直到新版本验证完全等价，再删
- **不改行为，只改结构**：重构期间不新增功能、不修无关 bug
- **任何一步翻车**：`git reset --hard bb54ef8` 回到起点

## 进度日志

### 2026-04-24 Phase 0
- 分支 `refactor-phase-0` 创建
- 骨架目录搭建：`web/src/{ui,app,domain,infra/{backend,storage}}` / `services/{file,auth,agents,finance,usage,perf}/lib` / `lib/{http,storage,logger}`
- REFACTOR.md 创建（本文档）
