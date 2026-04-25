# services/

This is the **authoritative source** for the local Node services that sit
beside the OpenClaw gateway. Before Phase 5 these files lived in `~/` (the
home directory), edited in place; they are now version-controlled here.

| Service | Port | Source | systemd-user unit | Purpose |
|---|---|---|---|---|
| file-api    | 7682 | `file/server.js`    | `file-api.service`    | Chat persistence, file browser, perf log shim |
| auth-server | 7683 | `auth/server.js`    | `auth-server.service` | Cookie auth gate (`/auth/*`) |
| finance-api | 7684 | `finance/server.js` | _(none — bare process)_ | Finance Agent backend |
| agents-api  | 7685 | `agents/server.js`  | `agents-api.service`  | Agents data (climbing, AI news, …) |
| usage-api   | 7686 | `usage/server.js`   | `usage-api.service`   | Token usage tracking |
| perf-api    | 7687 | `perf/server.js`    | _(none — bare process)_ | Frontend perf telemetry |

All units run under `systemd --user` (not the system instance — see the
2026-04-25 incident in `MEMORY.md` where 4 system-level units were
mis-installed). Source-of-truth lives in `~/.config/systemd/user/*.service`;
sanitized copies live in `services/systemd-user/`.

## Workflow

### Editing a service

```bash
# 1. Edit the version in repo
$EDITOR services/file/server.js

# 2. Run sync (does syntax check + diff + atomic copy + restart)
npm run services:sync          # all services
npm run services:sync file     # just one

# 3. Commit
git add services/file/server.js && git commit
```

### NEVER do this

- ❌ Edit `~/file-api-server.js` directly (drift from repo)
- ❌ Restart a service whose repo source hasn't passed `node --check`
- ❌ `kill` from `exec` — environment quirk SIGTERMs the parent (use
   `systemctl --user restart` or `systemd-run --on-active=2 …`)

### finance-api / perf-api — still bare

These two are currently launched as plain `node ...` processes (no systemd
unit). Phase 5.3 will promote them; until then `services:sync` only updates
the source file but does not restart them.

## Layout

```
services/
├── README.md                    # this file
├── systemd-user/                # sanitized unit files
│   ├── file-api.service
│   ├── auth-server.service
│   ├── agents-api.service
│   └── usage-api.service
├── file/      server.js  lib/   # one dir per service
├── auth/      server.js  lib/
├── agents/    server.js  lib/
├── usage/     server.js  lib/
├── finance/   server.js  lib/
└── perf/      server.js  lib/
```

`lib/` is reserved for future module extraction (same pattern as `web/src/`).
Today every service is one file — same as before, just under version control.
