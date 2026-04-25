#!/usr/bin/env node
// scripts/sync-units.mjs — sync repo services/systemd-user/*.service
// → ~/.config/systemd/user/*.service.
//
// Pairs with services/<name>/server.js (Phase 5.1). The .service files
// reference absolute paths to ~/<name>.js, which sync-services.mjs maintains.
//
// Usage:
//   node scripts/sync-units.mjs                     # check + diff + copy
//   node scripts/sync-units.mjs file-api auth-server
//   node scripts/sync-units.mjs --dry-run
//   node scripts/sync-units.mjs --reload            # also `systemctl --user daemon-reload`
//
// SAFETY:
//   1. Validate every unit BEFORE writing — must have [Service] + ExecStart=.
//      One failure = abort all (no copy, no reload).
//   2. Atomic write (tmp + rename).
//   3. Byte-identical files are NOT touched.
//   4. Does NOT restart services. After --reload, run `services:deploy` or
//      `systemctl --user restart <unit>` manually.

import { readFileSync, writeFileSync, statSync, renameSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const HOME = homedir();
const SRC_DIR = join(repoRoot, 'services', 'systemd-user');
const DST_DIR = join(HOME, '.config', 'systemd', 'user');

const RED = '\x1b[31m', GREEN = '\x1b[32m', YELLOW = '\x1b[33m', DIM = '\x1b[2m', RESET = '\x1b[0m';
const ok   = (m) => console.log(`${GREEN}✓${RESET} ${m}`);
const warn = (m) => console.log(`${YELLOW}!${RESET} ${m}`);
const dim  = (m) => console.log(`${DIM}${m}${RESET}`);
const fail = (m) => { console.error(`${RED}✗ ${m}${RESET}`); process.exit(1); };

// All .service files we manage. Add a new entry here when promoting a
// bare process to a systemd unit (Phase 5.3 will add finance / perf).
const UNITS = [
  'file-api.service',
  'auth-server.service',
  'agents-api.service',
  'usage-api.service',
  'finance-api.service',
  'perf-api.service',
];

const args = process.argv.slice(2);
const flags = new Set(args.filter(a => a.startsWith('--')));
const wanted = args.filter(a => !a.startsWith('--'));
const RELOAD = flags.has('--reload');
const DRY    = flags.has('--dry-run');

const targets = wanted.length
  ? wanted.map(n => {
      const u = n.endsWith('.service') ? n : `${n}.service`;
      if (!UNITS.includes(u)) fail(`unknown unit: ${u} (known: ${UNITS.join(', ')})`);
      return u;
    })
  : UNITS;

console.log(`${YELLOW}→ sync-units: ${targets.join(', ')}${RELOAD ? ' (will daemon-reload)' : ''}${DRY ? ' [DRY-RUN]' : ''}${RESET}`);

// ── 1. validate every target ──────────────────────────────────────────
function validateUnit(buf, name) {
  const text = buf.toString('utf8');
  const errors = [];
  if (!/^\[Service\]/m.test(text))     errors.push('missing [Service] section');
  if (!/^ExecStart=\S/m.test(text))    errors.push('missing ExecStart=');
  // [Install] is recommended but not strictly required (Type=oneshot etc.)
  // Detect obviously broken state: stray CRLF, BOM
  if (text.charCodeAt(0) === 0xFEFF)   errors.push('starts with BOM (will confuse systemd)');
  return errors;
}

let valErrs = 0;
for (const u of targets) {
  const sp = join(SRC_DIR, u);
  let buf;
  try { buf = readFileSync(sp); }
  catch (e) { console.error(`${RED}✗ ${u}: ${e.message}${RESET}`); valErrs++; continue; }
  const errs = validateUnit(buf, u);
  if (errs.length) {
    valErrs++;
    console.error(`${RED}✗ ${u}:${RESET}`);
    for (const e of errs) console.error(`    - ${e}`);
  }
}
if (valErrs) fail(`${valErrs} unit(s) failed validation; aborting (no copy, no reload)`);
ok(`validation OK (${targets.length} unit(s))`);

// ── 2. diff + atomic copy ─────────────────────────────────────────────
let copied = 0, unchanged = 0;
const changed = [];
for (const u of targets) {
  const sp = join(SRC_DIR, u);
  const dp = join(DST_DIR, u);
  const srcBuf = readFileSync(sp);
  let dstBuf = null;
  try { dstBuf = readFileSync(dp); } catch { /* missing — will create */ }
  if (dstBuf && srcBuf.equals(dstBuf)) {
    unchanged++;
    dim(`  = ${u} (unchanged)`);
    continue;
  }
  if (DRY) {
    warn(`  + would write ${dp} (${srcBuf.length} bytes)`);
    continue;
  }
  const tmp = dp + `.tmp.${process.pid}`;
  writeFileSync(tmp, srcBuf);
  renameSync(tmp, dp);
  copied++;
  changed.push(u);
  ok(`  ${u} → ${dp} (${srcBuf.length} bytes)`);
}
ok(`copy: ${copied} written, ${unchanged} unchanged`);

// ── 3. optional daemon-reload ─────────────────────────────────────────
if (RELOAD && !DRY && copied > 0) {
  const r = spawnSync('systemctl', ['--user', 'daemon-reload'], { encoding: 'utf8' });
  if (r.status !== 0) {
    console.error(`${RED}✗ daemon-reload failed:${RESET} ${r.stderr || r.stdout}`);
    process.exit(1);
  }
  ok('systemctl --user daemon-reload');
} else if (RELOAD && copied === 0) {
  dim('  (nothing changed — skipping daemon-reload)');
}

if (!DRY && copied > 0 && !RELOAD) {
  console.log(`${YELLOW}note:${RESET} units copied but daemon was NOT reloaded. Either:`);
  console.log(`  npm run units:sync -- --reload`);
  console.log(`  systemctl --user daemon-reload`);
  if (changed.length) {
    console.log(`then restart affected services:`);
    for (const u of changed) console.log(`  systemctl --user restart ${u}`);
  }
}
