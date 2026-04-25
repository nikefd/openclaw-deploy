#!/usr/bin/env node
// scripts/sync-services.mjs — sync repo services/ → ~/ + (optional) restart.
//
// Phase 5.1: source of truth is now `services/<name>/server.js` in repo.
// This script copies them to the legacy paths under $HOME (where systemd
// units expect them) — atomic, with syntax check per file.
//
// Usage:
//   node scripts/sync-services.mjs                # check + diff + copy ALL
//   node scripts/sync-services.mjs file auth      # only listed
//   node scripts/sync-services.mjs --restart      # also `systemctl --user restart`
//   node scripts/sync-services.mjs --dry-run      # report only, no writes
//
// SAFETY:
//   1. node --check every file BEFORE any copy. One failure = abort all.
//   2. Atomic write (write tmp, rename).
//   3. Restart is opt-in; finance/perf have no unit, restart silently skipped.
//   4. Will not touch a file when content is byte-identical (no spurious mtime).

import { readFileSync, writeFileSync, copyFileSync, statSync, renameSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { homedir } from 'node:os';

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const HOME = homedir();

const RED = '\x1b[31m', GREEN = '\x1b[32m', YELLOW = '\x1b[33m', DIM = '\x1b[2m', RESET = '\x1b[0m';
const ok   = (m) => console.log(`${GREEN}✓${RESET} ${m}`);
const warn = (m) => console.log(`${YELLOW}!${RESET} ${m}`);
const dim  = (m) => console.log(`${DIM}${m}${RESET}`);
const fail = (m) => { console.error(`${RED}✗ ${m}${RESET}`); process.exit(1); };

// name → { src (in repo), dst (in $HOME), unit (systemd-user, optional) }
const SERVICES = {
  file:    { src: 'services/file/server.js',    dst: 'file-api-server.js',    unit: 'file-api.service' },
  auth:    { src: 'services/auth/server.js',    dst: 'auth-server.js',        unit: 'auth-server.service' },
  agents:  { src: 'services/agents/server.js',  dst: 'agents-api.js',         unit: 'agents-api.service' },
  usage:   { src: 'services/usage/server.js',   dst: 'usage-api.js',          unit: 'usage-api.service' },
  finance: { src: 'services/finance/server.js', dst: 'finance-api-server.js', unit: null /* bare process */ },
  perf:    { src: 'services/perf/server.js',    dst: 'perf-api.js',           unit: null /* bare process */ },
};

// ── parse args ─────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const flags = new Set(args.filter(a => a.startsWith('--')));
const wanted = args.filter(a => !a.startsWith('--'));
const RESTART = flags.has('--restart');
const DRY     = flags.has('--dry-run');

const targets = wanted.length
  ? wanted.map(n => { if (!SERVICES[n]) fail(`unknown service: ${n} (known: ${Object.keys(SERVICES).join(', ')})`); return n; })
  : Object.keys(SERVICES);

// ── 1. syntax check all targets ────────────────────────────────────────
console.log(`${YELLOW}→ sync-services: ${targets.join(', ')}${RESTART ? ' (will restart)' : ''}${DRY ? ' [DRY-RUN]' : ''}${RESET}`);
let synErrs = 0;
for (const name of targets) {
  const sp = join(repoRoot, SERVICES[name].src);
  const r = spawnSync(process.execPath, ['--check', sp], { encoding: 'utf8' });
  if (r.status !== 0) {
    synErrs++;
    console.error(`${RED}✗ ${SERVICES[name].src}:${RESET}`);
    console.error((r.stderr || '').split('\n').slice(0, 5).join('\n'));
  }
}
if (synErrs) fail(`${synErrs} file(s) failed --check; aborting (no copy, no restart)`);
ok(`syntax OK (${targets.length} file(s))`);

// ── 2. diff + atomic copy ──────────────────────────────────────────────
let copied = 0, unchanged = 0;
for (const name of targets) {
  const sp = join(repoRoot, SERVICES[name].src);
  const dp = join(HOME, SERVICES[name].dst);
  const srcBuf = readFileSync(sp);
  let dstBuf = null;
  try { dstBuf = readFileSync(dp); } catch { /* missing — will create */ }
  if (dstBuf && srcBuf.equals(dstBuf)) {
    unchanged++;
    dim(`  = ${name.padEnd(8)} ${dp} (unchanged)`);
    continue;
  }
  if (DRY) {
    warn(`  + ${name.padEnd(8)} would write ${dp} (${srcBuf.length} bytes)`);
    continue;
  }
  // atomic write
  const tmp = dp + `.tmp.${process.pid}`;
  writeFileSync(tmp, srcBuf);
  renameSync(tmp, dp);
  copied++;
  ok(`  ${name.padEnd(8)} → ${dp} (${srcBuf.length} bytes)`);
}
ok(`copy: ${copied} written, ${unchanged} unchanged`);

// ── 3. optional restart ────────────────────────────────────────────────
if (RESTART && !DRY) {
  let restarted = 0, skipped = 0;
  for (const name of targets) {
    const unit = SERVICES[name].unit;
    if (!unit) { warn(`  ⊘ ${name.padEnd(8)} no systemd unit (bare process — skip)`); skipped++; continue; }
    const r = spawnSync('systemctl', ['--user', 'restart', unit], { encoding: 'utf8' });
    if (r.status !== 0) {
      console.error(`${RED}✗ restart ${unit}:${RESET} ${r.stderr || r.stdout}`);
    } else {
      restarted++;
      ok(`  ↻ restarted ${unit}`);
    }
  }
  console.log(`${GREEN}restart: ${restarted} ok, ${skipped} skipped${RESET}`);
}

if (!DRY && copied > 0 && !RESTART) {
  console.log(`${YELLOW}note:${RESET} files copied but services NOT restarted. Run again with --restart, or:`);
  for (const n of targets) {
    const u = SERVICES[n].unit;
    if (u) console.log(`  systemctl --user restart ${u}`);
  }
}
