# OpenClaw Deploy — zhangyangbin.com

自建 ChatGPT 风格 AI 助手平台，基于 [OpenClaw](https://github.com/openclaw/openclaw) Gateway。集成多个专项 Agent、金融交易系统、攀岩训练追踪、面试教练、AI 前沿资讯聚合等功能。

## ✨ 功能亮点

### 💬 聊天核心
- ChatGPT 风格对话界面 — Markdown 渲染、代码高亮、LaTeX 公式
- 文件上传（拖拽/点击，图片+文档）
- 语音输入（Web Speech API）
- 对话历史持久化（服务端存储）
- 暗色/亮色主题 · 移动端适配

### 🤖 Agent 生态 (`/agents/`)
| Agent | 功能 |
|-------|------|
| 🤖 **AI 前沿追踪** | 每日自动抓取 10+ 源的 AI 新闻，自定义 Track 过滤，带「动手试试」实操建议，内置学习中心 |
| 🧗 **攀岩教练** | 训练数据记录、进步趋势图表（Chart.js）、难度分布分析、AI 瓶颈诊断 |
| 🎯 **面试刷题教练** | 算法题 + 系统设计模拟面试，出题→答题→AI 点评→进度追踪 |
| 💰 **A股金融 Agent** | AI 选股 + 模拟盘自动交易 + 情绪指数 + 每日盘后分析报告 |
| 🎨 **Vibe Coding** | 限时编程挑战，AI 自动评测打分 |

### 🔐 认证 & 分享
- 密码登录 + Cookie Session
- Demo 码系统 — 生成带过期时间的分享码，让朋友体验

### 📊 运维监控
- Token 用量 Dashboard（按日/模型/Agent 维度统计+费用估算）
- 性能监控面板（服务器状态、响应时间）
- 系统架构可视化
- Web 终端（ttyd，浏览器直接操作服务器）

## 🏗 架构

```
Nginx (443/80)
├── /              → 聊天界面 (index.html)
├── /agents/       → Agent 管理面板 (agents.html)
├── /finance       → 金融 Agent 独立页面
├── /login         → 登录页
├── /usage.html    → Token Dashboard
├── /perf.html     → 性能监控
├── /architecture  → 架构图
├── /v1/           → OpenClaw Gateway API (18789)
├── /terminal      → ttyd Web 终端 (7681)
├── /api/files/    → 文件上传 API (7682)
├── /api/usage/    → Token 用量 API (7684)
├── /api/agents/   → Agent 数据 API (7685)
├── /auth/         → 认证服务 (7683)
├── /demos/        → Demo 应用（无需认证）
└── /dashboard/    → OpenClaw 原版控制台 (18789)
```

## 📁 目录结构

```
openclaw-deploy/
├── auth-server.js              # 认证服务：登录、session、demo 码
├── file-api-server.js          # 文件上传 API
├── usage-api.js                # Token 用量聚合 API
├── agents-api.js               # Agent 数据 API（攀岩、AI新闻等）
├── finance-api-server.js       # 金融 Agent API
├── finance-agent/              # 🔥 A股金融交易系统
│   ├── config.py               #   配置（API Key、策略参数）
│   ├── stock_picker.py         #   AI 选股引擎
│   ├── signal_analysis.py      #   多维信号分析
│   ├── trading_engine.py       #   交易引擎
│   ├── real_trader.py          #   实盘/模拟盘交易
│   ├── real_scheduler.py       #   交易日调度器
│   ├── position_manager.py     #   持仓管理
│   ├── ai_analyst.py           #   AI 分析师（新闻+研报解读）
│   ├── news_collector.py       #   新闻采集
│   ├── data_collector.py       #   行情数据采集
│   ├── market_data_ext.py      #   扩展行情数据
│   ├── market_regime.py        #   市场状态判断
│   ├── datasource_monitor.py   #   数据源监控
│   ├── backtester.py           #   回测框架
│   ├── performance_tracker.py  #   绩效追踪
│   ├── strategies/             #   交易策略集合
│   ├── data/                   #   历史数据
│   └── reports/                #   分析报告
├── deploy.sh                   # 部署脚本
├── rollback.sh                 # 回滚脚本
├── nginx/
│   ├── openclaw.conf           #   生产 Nginx 配置
│   └── openclaw.conf.template  #   模板
├── systemd/
│   ├── auth-server.service     #   认证服务 (7683)
│   ├── file-api.service        #   文件上传 (7682)
│   ├── usage-api.service       #   用量 API (7684)
│   ├── agents-api.service      #   Agent 数据 API (7685)
│   ├── ttyd.service            #   Web 终端 (7681)
│   └── openclaw.service.template
├── web/
│   ├── index.html              #   主聊天界面
│   ├── login.html              #   登录页
│   ├── agents.html             #   Agent 管理面板
│   ├── finance.html            #   金融 Agent 页面
│   ├── dashboard.html          #   概览仪表盘
│   ├── usage.html              #   Token Dashboard
│   ├── perf.html               #   性能监控
│   ├── architecture.html       #   架构可视化
│   ├── demo-login.html         #   Demo 码入口
│   ├── vibe.html               #   Vibe Coding 页面
│   ├── auth-ok.json            #   认证检查响应
│   └── demos/                  #   Demo 应用
│       └── village/
└── scripts/
    └── healthcheck.sh
```

## 🧠 Agent 系统架构

本平台的核心是一个完整的 **AI Agent 系统**，支持工具调用、多层记忆、多 Session 协作。

### 工具调用（Tool Use）

```
用户消息 → LLM 判断是否需要调用工具
                ↓ 是
        输出结构化 Function Call（JSON Schema）
                ↓
        框架解析 → 执行函数（查 API / 读文件 / 操作数据库）
                ↓
        结果回传 LLM → 生成最终回复
```

- 每个工具通过 JSON Schema 声明入参，LLM 自主选择调用
- 敏感操作（删除、支付）需人工审批（approval gate）
- 支持工具链式调用：一次对话中 Agent 可连续调用多个工具完成复杂任务
- 示例：金融 Agent 调用 行情API → 信号分析 → 交易引擎，全链路自主 planning

### 上下文与记忆（Context & Memory）

三层记忆架构：

| 层级 | 实现 | 说明 |
|------|------|------|
| **短期记忆** | 当前 Session 对话历史（滑动窗口） | 控制 token 消耗，保持对话连贯 |
| **中期记忆** | 每日日志 `memory/YYYY-MM-DD.md` | 当天事件、决策、进展的原始记录 |
| **长期记忆** | `MEMORY.md` + 语义检索 | 用户画像、偏好、历史重要决策 |

关键设计：
- **语义检索（memory_search）**：不全量加载记忆，根据当前问题搜索相关片段注入 prompt
- **上下文隔离**：不同 Agent 各自维护独立状态
- **Session 持久化**：服务端存储，跨重启不丢失

### 多 Session 与多 Agent 协作

```
┌─────────────────────────────────────────┐
│            主 Session（用户对话）          │
│  ┌──────────┐  ┌──────────┐             │
│  │ @攀岩教练 │  │ @金融Agent│  ← 路由切换  │
│  └──────────┘  └──────────┘             │
│        ↓ spawn                          │
│  ┌──────────────────┐                   │
│  │ 子 Agent Session  │ ← 隔离执行，完成汇报│
│  └──────────────────┘                   │
└─────────────────────────────────────────┘
        ↕ 跨 session 通信
┌──────────────────┐
│ 定时任务 Session   │ ← Cron 触发（金融日报、记忆整理）
└──────────────────┘
```

- **主 Session**：用户直接对话，完整上下文
- **子 Agent**：spawn 隔离子任务（如 JD 分析、简历匹配），完成后结果回传
- **定时任务**：Cron 驱动独立 Session（每日金融分析、记忆整理）
- **跨 Session 通信**：Session 间可 send 消息实现协作
- **@mention 路由**：根据触发词切换 Agent Profile（system prompt + 工具集 + 知识库范围）

---

## 🚀 部署

### 前置条件

- Ubuntu 22.04+ / Debian 12+
- Node.js 20+、Python 3.10+
- 域名 DNS A 记录指向服务器
- sudo 权限

### 快速部署

```bash
git clone https://github.com/nikefd/openclaw-deploy.git
cd openclaw-deploy

# 1. 安装 OpenClaw
npm install -g openclaw
openclaw setup        # 首次配置
openclaw auth         # GitHub Copilot 认证

# 2. 部署 Web 文件
sudo mkdir -p /var/www/chat
sudo cp web/* /var/www/chat/
sudo cp -r web/demos /var/www/chat/

# 3. 部署后端服务
cp auth-server.js file-api-server.js usage-api.js agents-api.js finance-api-server.js ~/
mkdir -p ~/.config/systemd/user
cp systemd/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now auth-server file-api usage-api

# 4. Nginx
sudo cp nginx/openclaw.conf /etc/nginx/sites-available/
sudo cp nginx/openclaw.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 5. HTTPS
sudo certbot --nginx -d yourdomain.com

# 6. 金融 Agent（可选）
cd finance-agent
pip install -r requirements.txt  # 如有
python real_scheduler.py         # 启动交易调度
```

### 配置

```bash
# 认证密码
# 编辑 auth-server.js 或在 systemd service 中设置：
Environment=AUTH_PASSWORD=your-password

# AI Provider（~/.openclaw/openclaw.json）
{
  "provider": { "kind": "github-copilot" }
}
# GitHub Copilot 订阅用户可免费使用 Claude、GPT-4o 等模型
```

## 🔌 服务端口

| 端口 | 服务 | 说明 |
|------|------|------|
| 18789 | OpenClaw Gateway | AI Agent 核心 |
| 7681 | ttyd | Web 终端 |
| 7682 | file-api-server | 文件上传 |
| 7683 | auth-server | 登录认证 + Demo 码 |
| 7684 | usage-api | Token 用量统计 |
| 7685 | agents-api | Agent 数据（攀岩、AI新闻等） |

## 🛠 管理命令

```bash
# 服务状态
systemctl --user status auth-server file-api usage-api

# OpenClaw
openclaw status
openclaw gateway status

# 日志
journalctl --user -u openclaw-gateway -f
journalctl --user -u auth-server -f
sudo journalctl -u nginx -f
```

## 🔍 故障排查

| 问题 | 排查 |
|------|------|
| 502 Bad Gateway | `systemctl --user status openclaw-gateway` |
| 登录失败 | `systemctl --user status auth-server` + 检查密码 |
| 文件上传失败 | `systemctl --user status file-api` + 检查 `client_max_body_size` |
| Token Dashboard 无数据 | `systemctl --user status usage-api` |
| Agent 数据加载失败 | `systemctl --user status agents-api` (7685) |
| WebSocket 断连 | 检查 Nginx `proxy_read_timeout` |

## 📦 迁移

1. Clone 本 repo
2. 按「快速部署」步骤操作
3. 拷贝 `~/.openclaw/` 目录（配置、session、记忆文件）
4. 拷贝 `~/agent-data/` 目录（Agent 数据：攀岩记录、AI新闻等）
5. 重新运行 `openclaw auth`

## License

MIT
