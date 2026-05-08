# @oc/server

Phase B (`refactor-v2/phase-b-comms`) introduces the Socket.IO `/chat-run`
namespace on top of the Phase A scaffold.

## Run locally

```bash
# from repo root
MOCK_UPSTREAM=1 npm run -w @oc/server dev
```

Listens on `http://127.0.0.1:8001` by default. The client (vite dev on
:5174) proxies `/socket.io` here automatically.

## Tests

```bash
MOCK_UPSTREAM=1 npm run -w @oc/server test
```

Three vitest cases cover the happy path, resume-after-disconnect, and abort.
They spin up `socket.io` + `socket.io-client` in-memory (`server.listen(0)`).

## Environment

| Var | Default | Purpose |
| --- | --- | --- |
| `PORT` | `8001` | http listen port |
| `MOCK_UPSTREAM` | _unset_ | when `1`, `streamCopilot` emits 10 fake `token-N` deltas at 100ms cadence. Tests rely on this. |
| `OPENCLAW_COPILOT_URL` | `https://api.githubcopilot.com/chat/completions` | real upstream SSE endpoint |
| `OPENCLAW_COPILOT_TOKEN` | _unset_ | Bearer token for real upstream |
| `OPENCLAW_CHATS_DIR` | `~/agent-data/chats` | where `<sid>.json` files (and the new `events[]` array) live |

## Persistence

Each chat session has a JSON file at `<OPENCLAW_CHATS_DIR>/<sid>.json`.
Phase B does NOT alter the existing fields; it only adds an `events` array:

```jsonc
{
  // ...existing chatRepo fields...
  "events": [
    { "kind": "run.queued", "data": { "sid": "...", "runId": "...", "seq": 0 }, "seq": 0, "ts": 1731000000000 },
    { "kind": "message.delta", "data": { "...": "..." }, "seq": 1, "ts": 1731000000010 }
    // ...
  ]
}
```

Writes are debounced 200ms per-sid and committed via atomic rename so a
crash mid-write cannot truncate an existing chat file. The events array is
capped at 500 entries (rolling window) to bound file size.

## Nginx (proposed — DO NOT deploy from this branch)

When wiring the v2 client behind nginx, add the following alongside the
existing `/api/...` blocks. Make sure `/socket.io/` is reverse-proxied to
@oc/server with WebSocket upgrade and long-lived timeouts:

```nginx
# v2 socket.io upstream (Phase B)
location /socket.io/ {
    proxy_pass http://127.0.0.1:8001/socket.io/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Streaming chat runs can be long; disable buffering, give them an hour.
    proxy_buffering off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

This is intentionally **not** committed into
`/etc/nginx/sites-available/openclaw.conf` yet — Phase B is dev-only.

## File layout (Phase B additions)

```
src/
  index.ts                         # attaches the namespace
  services/
    chat-stream.ts                 # /chat-run handler (start/resume/abort)
    chat-events-store.ts           # debounced fs persistence + replay
    upstream/
      copilot-bridge.ts            # SSE bridge + MOCK_UPSTREAM mode
    __tests__/
      chat-stream.test.ts          # vitest happy/resume/abort
vitest.config.ts
```
