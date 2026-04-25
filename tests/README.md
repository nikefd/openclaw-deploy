# Tests

Lightweight, zero-dependency safety net for the chat frontend.

## What's here

- **`unit/`** — pure-function tests for `web/src/` modules. Run with Node's
  built-in `node --test`. **No npm install needed.**
- **`smoke/`** — bash + curl probes against a running deploy. Catches
  "did I break the static layout / nginx routing / sync to /var/www/chat"
  classes of bug in <2s.

## Usage

```bash
# everything
npm test

# just pure-function unit tests (~0.3s)
npm run test:unit

# just smoke probes against local nginx + filesystem + node services (~1s)
npm run test:smoke

# probe production
npm run test:smoke:remote
```

## Adding a test

### Unit (preferred when refactoring)

When you extract a pure function into `web/src/`, drop a matching test:

```
tests/unit/<module>.test.mjs
```

Use Node's built-ins only:

```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { yourFn } from '../../web/src/...';

test('describes the behavior', () => {
  assert.equal(yourFn(input), expected);
});
```

DOM-touching code (anything that reads `document` / `window`) needs minimal
stubs at the top of the file — see `markdown.test.mjs` for the pattern.

### Smoke

When you add a new module, append a `probe_file` line in `smoke.sh`:

```bash
probe_file "src/ui/your_new.js" 100 "export"
```

When you add a new local service, append `probe_alive`.

## Philosophy

- **Cheap & fast > comprehensive.** If `npm test` takes >5s nobody will run it.
- **Catch the bug class, not every bug.** Smoke catches "static didn't deploy"
  / "module is empty" / "service not listening". Unit catches "pure function
  returned wrong value".
- **No deps.** Node 18+ ships `node:test` and `node:assert/strict`. bash + curl
  are everywhere. We don't pull in jest / vitest / playwright unless we have to.
- **Phase-gate: E2E lives in the future.** Once Phase 4–6 land, we'll add
  Playwright for the "send a message, verify reply persists" full chain.

## What's NOT covered (yet)

- E2E: actual chat round-trip, streaming, persistence after reload.
- Visual regression: theme rendering, mobile layout.
- Backend services: file-api / perf-api / agents-api endpoint contracts.

These can come later. For now, **unit + smoke is enough to catch every
refactor regression we've seen so far** (nginx fallback loop, "deploy out of
sync", empty module, pure-function logic bug).
