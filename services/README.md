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

All 6 services run under `systemd --user` with `ExecStart` pointing
**directly at this repo path** (Phase 5.4 option C — no copy, repo == prod).
Sanitized copies of the unit files live in `services/systemd-user/`.

## Workflow

### Editing a service

```bash
# 1. Edit the source in repo
$EDITOR services/file/server.js

# 2. Validate before restart
node --check services/file/server.js
npm run test:unit            # add lib/ tests as you extract modules

# 3. Restart the service — it loads straight from this repo path
systemctl --user restart file-api.service
```

There is **no** `services:sync` step. The systemd unit's `ExecStart=` is
literally `/home/nikefd/openclaw-deploy/services/<name>/server.js`.

### Editing a unit file

```bash
$EDITOR services/systemd-user/file-api.service
npm run units:sync           # check + diff + atomic copy (no reload)
npm run units:reload         # ... and `systemctl --user daemon-reload`
systemctl --user restart file-api.service
```

### Adding a new service

1. Create `services/<name>/server.js` (any required `lib/` next to it).
2. Create `services/systemd-user/<name>.service` with
   `ExecStart=/usr/bin/node /home/nikefd/openclaw-deploy/services/<name>/server.js`.
3. Register in `scripts/sync-units.mjs` `UNITS`.
4. `npm run units:sync -- --reload && systemctl --user enable --now <name>`.
5. Add the unit to the smoke drift loop in `tests/smoke/smoke.sh`.

### NEVER do this

- ❌ Restart a service whose repo source hasn't passed `node --check`
- ❌ `kill` from `exec` — environment quirk SIGTERMs the parent (use
   `systemctl --user restart` or `systemd-run --on-active=2 …`)
- ❌ Move/rename `/home/nikefd/openclaw-deploy/` — 6 services depend on the path

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
