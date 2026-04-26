# Refactor Progress — index.html 解耦重构

> 跨会话续命用。每次开新对话先读这个文件，再读 MEMORY.md 当天日期对应章节。

**仓库**：`/home/nikefd/openclaw-deploy`
**分支**：`refactor-phase-0`
**目标**：把 ~3170 行的 `web/index.html` 拆成 clean architecture（infra / domain / ui 层），便于解耦 OpenClaw、独立测试。

---

## ✅ 已完成 phases（commit 顺序最新到最旧）

| Phase | 内容 | commit | tests |
|---|---|---|---|
| **streamRecovery** | visibility + reader-stale watchdog → `src/ui/streamRecovery.js`（`shouldRecover` 纯函数 + `createStreamRecovery` 工厂，reader 不进模块）；index.html module-first + inline fallback | `6206982` | +15 |
| **streamHandler** | SSE 解析纯化 → `src/ui/streamHandler.js`（parseStreamLine / extractDelta / appendDelta / splitBuffer），index.html SSE 循环嵌套 7 层→3 层、最长行 600→120 字符；后端 `services/file/server.js` idle timeout 30s→120s（opus 长回复假 idle 修复） | `a47db25` | +29 |
| **send-fix-3x** | 24h 内 `send()` 函数 3 连击 bug：`}}catch{}}}` 残留 / 修 1 删多 `}` / `let el=null` 被早期重构删了但注释还在 | `fd7bec2` → `4ecc425` → `94cb2cc` | — |
| **5.3** | finance / perf 从裸进程提升为 systemd-user unit | `003b5d4` | smoke +2 |
| **5.2** | `scripts/sync-units.mjs` 同步 .service 文件 + smoke 4 个 unit drift | `003b5d4` | smoke +4 |
| **5.1** | 后端 6 个 service 进 repo + `npm run services:sync` + smoke 6 个 drift | `48c2099` | smoke +6 |
| **4.12** | Tasks 看板 → `src/ui/tasksDashboard.js`（9 个 builder + agents.html 首接 module + sync-prod 扩到 agents.html） | `fe95fa0` | +32 |
| **4.11** | chat sidebar → `src/ui/chatSidebar.js`（groupLabel / groupHeaderHtml / chatItemHtml / emptyStateHtml，顺手补 agent 字段 escape） | `dd1142e` | +18 |
| **4.10** | `renderWelcome` → `src/ui/welcome.js`（welcomeHtml，纯字符串模板，含 mention chip 注入防御） | `ae48464` | +10 |
| **4.9** | `modelDropdownHtml` → `src/ui/modelDropdown.js`；顺手修 4.8 的 nodesPanel infra re-export 漏洞 | `3ddc541` | +9 |
| **safe-sync** | `scripts/sync-prod.mjs` + `npm run sync/deploy`，禁止裸 `cp → /var/www/chat/` | `af7f9ba` | dogfood ✓ |
| **4.8** | nodes panel HTML（pending/connected）→ `src/ui/nodesPanel.js` | `9cdd4e8` | +21 |
| **chat-fix** | 删 `tryRecover()`（4/24 gateway-history-overwrite bug 复发） | `b26837b` | — |
| **chat-fix** | `pollOne` signature check + file-api 启动自愈（chat 重刷 bug） | `3512267` | — |
| **4.7** | demo codes 卡片 → `src/ui/demoCodes.js` | `a86c126` | +17 |
| **4.6** | memory sidebar → `src/ui/memoryPanel.js` | `a3cec20` | +18 |
| **4.5** | chat search helpers → `src/ui/searchHelpers.js` | `8b52247` | +20 |
| **test infra** | unit + smoke 测试框架（zero-dep） | `b06588d` | 46+20 |
| **4.4** | skills panel → `src/ui/skillsPanel.js` | `21a2303` | — |
| **4.3** | file panel → `src/ui/fileHelpers.js` | `82f0927` | — |
| **4.2** | TTS → `src/ui/tts.js` | `4ede3d7` | — |
| **4.1** | markdown / messageActions → `src/ui/` | `788d9c6` | — |
| **3.5** | 纯 chat shape 逻辑 → `domain/chat.js` | `8dd8cdb` | — |
| 0–3.4 | 骨架 / CSS 抽离 / infra 层骨干 / SSE wire 统一 | 多个 | — |

**当前测试**：458 unit + 34 smoke 全绿（2026-04-26 streamRecovery 后）

---

## 📐 架构 / 文件布局

```
openclaw-deploy/
├── web/
│   ├── index.html          # 应用主入口（~2128 行，从 3170 减下来的）
│   ├── login.html
│   ├── assets/css/app.css  # Phase 1 抽出来的样式
│   └── src/
│       ├── infra/          # 基础设施（config / backend / storage / telemetry）
│       │   └── index.js    # ★ 统一 export，挂到 window.__oc 供 index.html 调
│       ├── domain/         # 领域逻辑
│       │   └── chat.js     # 纯 chat shape 函数
│       └── ui/             # UI 渲染（HTML 字符串构造，纯函数）
│           ├── markdown.js
│           ├── messageActions.js
│           ├── tts.js
│           ├── fileHelpers.js
│           ├── skillsPanel.js
│           ├── searchHelpers.js
│           ├── memoryPanel.js
│           ├── demoCodes.js
│           ├── nodesPanel.js
│           ├── modelDropdown.js
│           ├── welcome.js
│           ├── chatSidebar.js
│           └── tasksDashboard.js   # agents.html 首个接入的 module
├── scripts/
│   └── sync-prod.mjs       # ★ 安全部署：先 syntax-check 再拷
├── tests/
│   ├── unit/*.test.mjs     # node:test，纯函数测试
│   └── smoke/smoke.sh      # bash，HTTP/文件存在性
└── package.json
```

**npm scripts**：
- `npm test` — unit + smoke（不部署）
- `npm run sync` — 仅安全部署（先 syntax-check）
- `npm run deploy` — `test:unit && sync && test:smoke`（**唯一推荐部署方式**）

---

## 🔧 重构标准模板（每个 phase 都这么干）

1. 在 `web/index.html` 找一个**纯字符串/纯计算**的渲染块（注意挑没有副作用的）
2. 创建 `web/src/ui/<name>.js`，导出 pure function
3. 写 `tests/unit/<name>.test.mjs`（覆盖：空入参、正常入参、HTML escape、边界 case）
4. 在 `web/src/infra/index.js` 加 import + export + `window.__oc.ui.<name>`
5. **改 index.html 用 module-first + inline fallback 模式**：
   ```js
   const m = window.__oc?.ui?.<name>;
   if (m?.<func>) {
     dst.innerHTML = m.<func>(args);
   } else {
     // 原始内联实现保留
   }
   ```
6. `npm run deploy`（必走，不要直接 cp）
7. 在 commit message 写清楚：
   - phase 编号
   - 抽出的函数列表
   - 测试覆盖了什么
   - 行为零变化
   - 任何踩坑（hairy moment）

---

## 🚨 雷区清单（必读）

0. **改 JS 一律先 `node --check`，更应该走 `npm run sync`**（2026-04-26 新增）— 同一函数 24h 内连环 3 个 bug 全是凭眼数大括号翻车。`send()` 当时单行 600 字符 / 嵌套 7 层，肉眼 linter = 必死。**任何 JS 改动结束前必须 `node --check` 验证**
1. **永远不要 `cp xxx /var/www/chat/`** — 用 `npm run sync`。Phase 4.8 中间炸过 30 秒生产
2. **edit 大块时先 `git diff` 看 diff** — 多次出现 oldText 匹配错位置
3. **改 chat 流式相关代码先备份 `~/.openclaw/chats/`**
4. **不要在 `nginx try_files /index.html` fallback 的 location 下加 `<script type="module">`** — module 加载失败会 fallback 到 index.html，浏览器当 module 解析→无限重渲染。Phase 2 翻车过
5. **edit 工具的 oldText 必须**精确字节匹配，oldText 太长容易 fail；优先短 anchor + 多次小 edit
6. **`node --check x.js` 对 ESM 太宽松** — sloppy script 解析会放过 `garbage }}{{`。`sync-prod.mjs` 用 `--input-type=module --check -` 管道修了
7. **添加新 module 后必须 `infra/index.js` 里 import + export + `window.__oc.ui.xxx`**——否则 fallback 永远生效，新代码 dead。Phase 4.8 漏过一次
8. **抽出函数后旧的内联代码可以保留作 fallback**（防 module 加载失败），不一定要清
9. **如果要动产 .html 文件动之前，先 `git stash` + `diff -q /var/www/chat/x.html web/x.html`** 验证 repo 跟 prod 一致，避免覆盖掉之前手改的内容 (Phase 4.12 踩过 mtime 误报的坑)

---

## 🎯 下一步候选（Phase 4.10+）

按"风险低 / 收益高"排：

### A. **chat sidebar 渲染**（✅ 已完成 → 4.11）

### B. **`renderWelcome` 抽出**（✅ 已完成 → 4.10）

### C. **Tasks 看板渲染**（✅ 已完成 → 4.12）
- agents.html 是本项目第二个接入 ES module 的页面
- 它只单独 import `/src/ui/tasksDashboard.js`，不引 infra 整层（避免副作用扩散）
- sync-prod.mjs 现在也拷 `agents.html` + check 其 inline scripts

### D. **Phase 5 进展**（✅ 5.1 / 5.2 / 5.3 / 5.4 全部完成）
- Phase 5.1 ✅ `48c2099`：6 service 进 repo + sync-services
- Phase 5.2 ✅ `003b5d4`：sync-units (`units:sync` / `units:reload`)
- Phase 5.3 ✅ `003b5d4`：finance/perf 提升 systemd-user unit（6 个服务全被守护）
- Phase 5.4 ✅ `0a80809` + `70430dd`：抽 `stripHeavy` + `sendJson` → `services/file/lib/` 使用 option C（systemd ExecStart 指 repo）。部署从“cp 到 ~/”变 `git pull && systemctl restart`。
- Phase 5.5 待做：继续抽后端路由/handler/DB 到 `lib/`，重点 `services/file/server.js` (697) 和 `services/finance/server.js` (1439)

**建议起步：Phase 5.5（抽 file/server.js 里的 chat persistence handler）。**

---

### 🆕 send() 函数继续拆（streamHandler 之后的下一波，与 Phase 5.5 可并行）

位置：`web/index.html` 内 `async function send(...)`，约 line 1410-1620。
抽完 streamHandler 后剩余痛点（按风险低 / 收益高排序）：

#### B. `streamFinalize.js` ⭐ 推荐下一个
流式正常结束（写 chat.messages、save、renderMd、append actions）和错误结束（"⚠⏸ 连接中断" 气泡 + 重试）有大量重复。建议抽纯函数 `buildFinalAssistantMessage({chatMessages, full}) → 新 messages 数组`，DOM 装饰可保留在 index.html。

#### C. `streamPerf.js`
抽 TTFT / pause / streaming 三段计时为 `createPerfTracker(now=performance.now)` 状态机。当前散在主循环里（`_perfTTFT` / `_perfPauses` / `_perfStreaming` / `_perfHttpMs` / `perfLog`）。

#### D. 删除 ff (fly-forward) 死代码
旧轮询路径在 line ~1340-1410（自带独立 `let el=null`）。前置 `grep -rn 'ffEnabled\|/api/chat/send\b\|/api/chat/history\b'` 确认无活跃调用方再删。**做完 send() 能掉 70+ 行。**

#### E. send() 拆 3-4 个小函数
`prepareStreamRequest()` / `runStreamLoop()` / `finalizeOk()` / `finalizeErr()`。**最后做**——A/B/C/D 抽完边界才稳定。

#### 不要碰
- `services/file/server.js` 的 idle timer（已是 120s，2026-04-26 调过）
- chat.messages 写入语义（流式期间不写，结束后才写——4/24 commit `bb54ef8` 成果）
- `let el=null;` 声明（line ~1486，被多处闭包引用）
- `<script type="module" src="/src/infra/index.js">`（Phase 2 翻车入口）

---

## 📝 关键文件位置速查

- 主 HTML：`web/index.html`
- Infra 入口：`web/src/infra/index.js`
- 测试：`tests/unit/*.test.mjs`
- 安全部署脚本：`scripts/sync-prod.mjs`
- Smoke 脚本：`tests/smoke/smoke.sh`
- 生产路径：`/var/www/chat/`（**不要直接动**）

---

## 🧠 心态笔记

- 每个 phase 抽 1 个模块、9–25 个测试、20–60 行净变化，**保持小 PR 节奏**
- 一旦发现 bug（重刷、tryRecover），优先修 bug 再继续抽
- 不要追求一次抽很多——之前 Phase 2 一次性接 module script 直接炸
- 改完测试 + smoke 全绿才能 commit，**绝对不允许**红灯 commit

_Last updated: 2026-04-26 by 狗蛋（streamRecovery done，下一个建议 streamFinalize）_
