# OpenClaw One-Click Deploy

一键部署 [OpenClaw](https://github.com/openclaw/openclaw) AI 代理平台，通过 Nginx 反向代理对外提供服务。

## 前置条件

- Ubuntu 22.04+ / Debian 12+
- Node.js 20+（已安装 npm）
- 域名 DNS A 记录指向服务器公网 IP
- 有 sudo 权限的用户

## 一键部署

```bash
git clone https://github.com/<your-username>/openclaw-deploy.git
cd openclaw-deploy
cp .env.example .env    # 编辑 .env 填入你的域名和端口
chmod +x deploy.sh
./deploy.sh
```

## 目录结构

```
openclaw-deploy/
├── deploy.sh                  # 全自动部署脚本
├── rollback.sh                # 回滚脚本
├── .env.example               # 环境变量模板
├── .gitignore
├── LICENSE
├── README.md
├── systemd/
│   └── openclaw.service.template   # systemd 用户服务模板
├── nginx/
│   └── openclaw.conf.template      # Nginx 虚拟主机模板
└── scripts/
    └── healthcheck.sh              # 健康检查脚本
```

## 配置 AI Provider

OpenClaw 支持多种 AI 后端。编辑 `~/.openclaw/openclaw.json`：

### GitHub Copilot（默认）

```json
{
  "provider": {
    "kind": "github-copilot"
  }
}
```

运行 `openclaw auth` 完成 GitHub OAuth 登录。

### OpenAI / Anthropic

```json
{
  "provider": {
    "kind": "openai",
    "apiKey": "sk-..."
  }
}
```

## 开启 Session Memory

OpenClaw 默认带有 workspace 级文件记忆。如需增强：

1. 编辑 `~/.openclaw/workspace/AGENTS.md` 配置记忆策略
2. 创建 `~/.openclaw/workspace/memory/` 目录
3. Agent 会自动在 `memory/YYYY-MM-DD.md` 写入每日笔记
4. `MEMORY.md` 作为长期记忆自动维护

## 创建多个 Agent

在 `~/.openclaw/openclaw.json` 中配置多 agent：

```json
{
  "agents": {
    "code-agent": {
      "model": "github-copilot/claude-opus-4.6",
      "systemPrompt": "You are a senior software engineer..."
    },
    "ai-news-agent": {
      "model": "github-copilot/gpt-4o",
      "systemPrompt": "You track AI industry news..."
    },
    "market-research-agent": {
      "model": "github-copilot/claude-opus-4.6",
      "systemPrompt": "You analyze market trends..."
    }
  }
}
```

通过 cron job 或 session spawn 调用不同 agent。

## 健康检查

```bash
./scripts/healthcheck.sh
```

## 回滚

```bash
./rollback.sh
```

## 故障排查

| 问题 | 排查 |
|------|------|
| 502 Bad Gateway | `systemctl --user status openclaw-gateway` 检查服务是否运行 |
| 域名无法访问 | 检查 DNS A 记录是否指向服务器 IP |
| WebSocket 断连 | 检查 Nginx 配置中 `proxy_read_timeout` |
| 端口冲突 | `ss -tlnp \| grep 18789` 检查端口占用 |

查看日志：
```bash
journalctl --user -u openclaw-gateway -f     # OpenClaw 日志
sudo journalctl -u nginx -f                   # Nginx 日志
```

## HTTPS（推荐）

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d zhangyangbin.com
```

## 替换域名

1. 编辑 `.env` 中的 `DOMAIN=`
2. 重新运行 `./deploy.sh`

## License

MIT
