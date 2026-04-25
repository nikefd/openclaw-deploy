#!/usr/bin/env node
// scripts/sync-prod.mjs
// Safe sync: validate JS syntax in web/index.html before copying any
// asset into /var/www/chat/. Bails out at first error — never touches
// production with broken code.
//
// Run via `npm run sync`.

import { readFileSync, copyFileSync, mkdirSync, statSync, readdirSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const SRC_ROOT = join(repoRoot, 'web');
const DST_ROOT = '/var/www/chat';

const RED = '\x1b[31m', GREEN = '\x1b[32m', YELLOW = '\x1b[33m', RESET = '\x1b[0m';
const ok   = (m) => console.log(`${GREEN}✓${RESET} ${m}`);
const warn = (m) => console.log(`${YELLOW}!${RESET} ${m}`);
const fail = (m) => { console.error(`${RED}✗ ${m}${RESET}`); process.exit(1); };

// ────────────────────────────────────────────────────────────────
// 1) Extract every <script>…</script> block (skip src=) and node --check
// ────────────────────────────────────────────────────────────────
function checkInlineScripts(htmlPath) {
  const html = readFileSync(htmlPath, 'utf8');
  const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;
  let m, idx = 0, errs = 0;
  while ((m = re.exec(html))) {
    idx++;
    const body = m[1];
    if (!body.trim()) continue;
    const tmp = join(tmpdir(), `sync-check-${process.pid}-${idx}.js`);
    writeFileSync(tmp, body);
    const r = spawnSync(process.execPath, ['--check', tmp], { encoding: 'utf8' });
    if (r.status !== 0) {
      errs++;
      console.error(`${RED}✗ inline <script> #${idx} has a syntax error:${RESET}`);
      console.error(r.stderr.split('\n').slice(0, 10).join('\n'));
    }
  }
  if (errs) fail(`${errs} inline script(s) failed --check; aborting sync.`);
  ok(`inline scripts OK (${idx} block(s) checked)`);
}

// ────────────────────────────────────────────────────────────────
// 2) node --check every .js file we plan to ship
// ────────────────────────────────────────────────────────────────
function walk(dir, out = []) {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (e.isFile() && p.endsWith('.js')) out.push(p);
  }
  return out;
}

function checkJsModules(srcDir) {
  if (!safeStat(srcDir)) { warn(`no ${relative(repoRoot, srcDir)} dir, skipping module check`); return; }
  const files = walk(srcDir);
  let errs = 0;
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    const isModule = /^\s*(import|export)\b/m.test(src);
    let r;
    if (isModule) {
      // For ES modules, --check is too lenient (sloppy-script parse); use
      // a real parse via Function(...) wrapper inside `node --input-type=module -e`.
      // Cleanest: run the file under `node --input-type=module --check` via stdin.
      r = spawnSync(process.execPath, ['--input-type=module', '--check', '-'], {
        input: src, encoding: 'utf8',
      });
    } else {
      r = spawnSync(process.execPath, ['--check', f], { encoding: 'utf8' });
    }
    if (r.status !== 0) {
      errs++;
      console.error(`${RED}✗ ${relative(repoRoot, f)}:${RESET}`);
      console.error((r.stderr || '').split('\n').slice(0, 8).join('\n'));
    }
  }
  if (errs) fail(`${errs} module(s) failed --check; aborting sync.`);
  ok(`modules OK (${files.length} file(s) checked under ${relative(repoRoot, srcDir)})`);
}

function safeStat(p) { try { return statSync(p); } catch { return null; } }

// ────────────────────────────────────────────────────────────────
// 3) Copy: index.html + login.html + assets/ + src/ (only if present)
// ────────────────────────────────────────────────────────────────
function copyTree(srcDir, dstDir) {
  if (!safeStat(srcDir)) return 0;
  let n = 0;
  for (const e of readdirSync(srcDir, { withFileTypes: true })) {
    const sp = join(srcDir, e.name);
    const dp = join(dstDir, e.name);
    if (e.isDirectory()) {
      mkdirSync(dp, { recursive: true });
      n += copyTree(sp, dp);
    } else if (e.isFile()) {
      copyFileSync(sp, dp);
      n++;
    }
  }
  return n;
}

function copyFile(rel) {
  const sp = join(SRC_ROOT, rel);
  if (!safeStat(sp)) return false;
  const dp = join(DST_ROOT, rel);
  mkdirSync(dirname(dp), { recursive: true });
  copyFileSync(sp, dp);
  return true;
}

// ────────────────────────────────────────────────────────────────
// MAIN
// ────────────────────────────────────────────────────────────────
console.log(`${YELLOW}→ safe sync from ${relative(repoRoot, SRC_ROOT)} → ${DST_ROOT}${RESET}`);

if (!safeStat(DST_ROOT)) fail(`${DST_ROOT} not found (mounted? running on prod host?)`);

const indexHtml = join(SRC_ROOT, 'index.html');
if (!safeStat(indexHtml)) fail(`${indexHtml} missing`);

// Gates
checkInlineScripts(indexHtml);
const agentsHtml = join(SRC_ROOT, 'agents.html');
if (safeStat(agentsHtml)) checkInlineScripts(agentsHtml);
checkJsModules(join(SRC_ROOT, 'src'));

// Copy
let total = 0;
for (const f of ['index.html', 'login.html', 'agents.html']) if (copyFile(f)) total++;

// Recurse known asset dirs only (don't blindly nuke /var/www/chat)
for (const dir of ['assets', 'src']) {
  const sp = join(SRC_ROOT, dir);
  const dp = join(DST_ROOT, dir);
  if (!safeStat(sp)) continue;
  mkdirSync(dp, { recursive: true });
  total += copyTree(sp, dp);
}

ok(`sync complete: ${total} file(s) copied`);
