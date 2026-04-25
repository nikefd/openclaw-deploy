# services/

This is the **authoritative source** for the local Node services that sit
beside the OpenClaw gateway. Before Phase 5 these files lived in `~/` (the
home directory), edited in place; they are now version-controlled here.

| Service | Port | Source | systemd-user unit | Purpose |
|---|---|---|---|---|
| file-api    | 7682 | `file/server.js`    | `file-api.service`    | Chat persistence, file browser, perf log shim |
| auth-server | 7683 | `auth/server.js`    | `auth-server.service` | Cookie auth gate (`/auth/*`) |
| finance-api | 7684 | `finance/server.js` | `finance-api.service` | Finance Agent backend |
| agents-api  | 7685 | `agents/server.js`  | `agents-api.service`  | Agents data (climbing, AI news, …) |
| usage-api   | 7686 | `usage/server.js`   | `usage-api.service`   | Token usage tracking |
| perf-api    | 7687 | `perf/server.js`    | `perf-api.service`    | Frontend perf telemetry |

All 6 services run under `systemd --user` (Phase 5.3 promoted finance + perf
from bare processes). Source-of-truth for unit files lives in `~/.config/systemd/user/*.service`;
sanitized copies live in `services/systemd-user/`.

## Workflow

### Editing a service or unit

```bash
# Edit the service code
$EDITOR services/file/server.js
npm run services:sync          # check + diff + atomic copy (no restart)
npm run services:deploy        # ... and `systemctl --user restart`

# Edit a unit file
$EDITOR services/systemd-user/file-api.service
npm run units:sync             # check + diff + atomic copy (no reload)
npm run units:reload           # ... and `systemctl --user daemon-reload`
```

### Promoting a bare process to systemd-user (Phase 5.3 pattern)

1. Add `services/systemd-user/<name>.service` (copy `usage-api.service` as a
   template).
2. Register in `scripts/sync-units.mjs` `UNITS` and `scripts/sync-services.mjs`
   `SERVICES[<name>].unit`.
3. `npm run units:sync -- --reload`.
4. Atomic switch from a `systemd-run` transient (kill bare, then
   `systemctl --user enable --now <name>`) — NOT direct `kill` from `exec`
   (SIGTERM kills the OpenClaw exec parent, see MEMORY.md 2026-04-25).
5. Add the unit to the smoke sanity loop.

### NEVER do this

- ❌ Edit `~/file-api-server.js` directly (drift from repo)
- ❌ Restart a service whose repo source hasn't passed `node --check`
- ❌ `kill` from `exec` — environment quirk SIGTERMs the parent (use
   `systemctl --user restart` or `systemd-run --on-active=2 …`)

### finance-api / perf-api — promoted Phase 5.3

These are now managed by `systemd --user` like the rest. Restart with
`systemctl --user restart finance-api.service` or `npm run services:deploy`.

## Layout

```
services/
├── README.md                    # this file
├── systemd-user/                # 6 unit files
│   ├── file-api.service
│   ├── auth-server.service
│   ├── agents-api.service
│   ├── usage-api.service
│   ├── finance-api.service
│   └── perf-api.service
├── file/      server.js  lib/   # one dir per service
├── auth/      server.js  lib/
├── agents/    server.js  lib/
├── usage/     server.js  lib/
├── finance/   server.js  lib/
└── perf/      server.js  lib/
```

`lib/` is reserved for future module extraction (same pattern as `web/src/`).
Today every service is one file — same as before, just under version control.
