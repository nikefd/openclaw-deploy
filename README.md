# OpenClaw Deploy — zhangyangbin.com

自建 ChatGPT 风格 AI 聊天平台，基于 [OpenClaw](https://github.com/openclaw/openclaw) Gateway，带完整的认证、文件上传、语音输入、Demo 码分享、Token 用量追踪。

## 功能

- 💬 **ChatGPT 风格聊天界面** — 支持 Markdown 渲染、代码高亮、对话历史
- 📎 **文件上传** — 拖拽或点击上传，支持图片和文档
- 🎤 **语音输入** — 浏览器原生 Web Speech API
- 🔐 **登录认证** — 密码登录 + Cookie Session
- 🎟️ **Demo 码系统** — 生成带过期时间的分享码，让朋友体验
- 📊 **Token Usage Dashboard** — 每日/模型/Agent 维度的用量统计和费用估算
- 🌙 **暗色/亮色主题切换**
- 📱 **移动端适配**

## 架构

```
Nginx (443/80)
├── /              → 聊天界面 (/var/www/chat/index.html)
├── /login         → 登录页
├── /usage.html    → Token Dashboard
├── /v1/           → OpenClaw Gateway API (18789)
├── /terminal      → ttyd Web 终端 (7681)
├── /api/files/    → 文件上传 API (7682)
├── /api/usage/    → Token 用量 API (7684)
├── /auth/         → 认证服务 (7683)
├── /demos/        → Demo 应用 (无需认证)
└── /dashboard/    → OpenClaw 原版控制台 (18789)
```

## 目录结构

```
openclaw-deploy/
├── auth-server.js          # 认证服务：登录、session、demo码管理
├── file-api-server.js      # 文件上传 API
├── usage-api.js            # Token 用量聚合 API
├── deploy.sh               # 部署脚本
├── rollback.sh             # 回滚脚本
├── nginx/
│   ├── openclaw.conf           # 生产 Nginx 配置
│   └── openclaw.conf.template  # 模板
├── systemd/
│   ├── auth-server.service     # 认证服务 (7683)
│   ├── file-api.service        # 文件上传 (7682)
│   ├── usage-api.service       # 用量 API (7684)
│   ├── ttyd.service            # Web 终端 (7681)
│   └── openclaw.service.template
├── web/
│   ├── index.html              # 主聊天界面
│   ├── login.html              # 登录页
│   ├── demo-login.html         # Demo 码入口
│   ├── usage.html              # Token Dashboard
│   ├── auth-ok.json            # 认证检查响应
│   └── demos/                  # Demo 应用
│       └── village/
└── scripts/
    └── healthcheck.sh
```

## 部署

### 前置条件

- Ubuntu 22.04+ / Debian 12+
- Node.js 20+
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

# 3. 部署服务
cp auth-server.js file-api-server.js usage-api.js ~/
mkdir -p ~/.config/systemd/user
cp systemd/auth-server.service systemd/file-api.service \
   systemd/usage-api.service systemd/ttyd.service \
   ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now auth-server file-api usage-api

# 4. Nginx
sudo cp nginx/openclaw.conf /etc/nginx/sites-available/
sudo cp nginx/openclaw.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 5. HTTPS
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### 配置认证密码

编辑 `auth-server.js` 中的密码配置，或设置环境变量：

```bash
# 在 auth-server.service 中添加
Environment=AUTH_PASSWORD=your-password
```

### 配置 AI Provider

编辑 `~/.openclaw/openclaw.json`：

```json
{
  "provider": {
    "kind": "github-copilot"
  }
}
```

GitHub Copilot 订阅用户可以免费使用多种模型（Claude、GPT-4o 等），性价比极高。

## 服务端口

| 端口 | 服务 | 说明 |
|------|------|------|
| 18789 | OpenClaw Gateway | AI Agent 核心 |
| 7681 | ttyd | Web 终端 |
| 7682 | file-api-server | 文件上传 |
| 7683 | auth-server | 登录认证 + Demo 码 |
| 7684 | usage-api | Token 用量统计 |

## 管理命令

```bash
# 查看所有服务状态
systemctl --user status auth-server file-api usage-api openclaw-gateway

# 查看 OpenClaw 状态
openclaw status
openclaw gateway status

# 查看日志
journalctl --user -u openclaw-gateway -f
journalctl --user -u auth-server -f
sudo journalctl -u nginx -f

# Demo 码管理（通过聊天界面的管理面板操作）
```

## 故障排查

| 问题 | 排查 |
|------|------|
| 502 Bad Gateway | `systemctl --user status openclaw-gateway` |
| 登录失败 | `systemctl --user status auth-server` + 检查密码 |
| 文件上传失败 | `systemctl --user status file-api` + 检查 `client_max_body_size` |
| Token Dashboard 无数据 | `systemctl --user status usage-api` + 检查 session 文件 |
| WebSocket 断连 | 检查 Nginx `proxy_read_timeout` |

## 迁移到新机器

1. Clone 本 repo
2. 按「快速部署」步骤操作
3. 拷贝 `~/.openclaw/` 目录（包含配置、session 历史、记忆文件）
4. 重新运行 `openclaw auth` 认证

## License

MIT
