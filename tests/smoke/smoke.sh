#!/usr/bin/env bash
# tests/smoke/smoke.sh — fast sanity probes for the deploy.
#
# Usage:
#   bash tests/smoke/smoke.sh                            # local nginx + filesystem
#   bash tests/smoke/smoke.sh https://zhangyangbin.com   # remote (auth_request → 302 to /login is OK)
#
# What we check:
#  - nginx is reachable & answers (200 or 302→login both fine — proves vhost works)
#  - Filesystem layer: /var/www/chat/ has all expected static files, non-empty
#  - JS module files actually contain `export` (not stale empties)
#  - Local Node services are listening on their ports

set -u
BASE="${1:-}"
PASS=0; FAIL=0; FAILED_NAMES=()

c_red()   { printf "\033[31m%s\033[0m" "$1"; }
c_green() { printf "\033[32m%s\033[0m" "$1"; }
c_dim()   { printf "\033[2m%s\033[0m" "$1"; }

if [ -z "$BASE" ]; then
  BASE="http://127.0.0.1"
  CURL_OPTS=(-sSk -H "Host: zhangyangbin.com" --max-time 8)
  MODE="local"
  WEBROOT="/var/www/chat"
else
  CURL_OPTS=(-sSk --max-time 8)
  MODE="remote"
  WEBROOT=""
fi

ok()   { c_green "PASS"; printf "  %s\n" "$1"; PASS=$((PASS+1)); }
fail() { c_red "FAIL"; printf "  %s\n" "$1"; printf "       %s\n" "$2"; FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); }

# probe_status NAME PATH ALLOWED_STATUSES (space-separated, e.g. "200 302")
probe_status() {
  local name="$1" url="$BASE$2" allowed="$3"
  local code
  code=$(curl "${CURL_OPTS[@]}" -o /dev/null -w "%{http_code}" "$url" 2>/dev/null) || code="000"
  for want in $allowed; do
    if [ "$code" = "$want" ]; then ok "$name (HTTP $code)"; return; fi
  done
  fail "$name" "$url -> status=$code, allowed=$allowed"
}

# probe_file PATH MIN_BYTES SUBSTRING — read file from disk, check size + content
probe_file() {
  local rel="$1" minb="$2" want="$3"
  local full="$WEBROOT/$rel"
  if [ ! -f "$full" ]; then fail "fs $rel" "$full not found"; return; fi
  local size
  size=$(stat -c%s "$full" 2>/dev/null || stat -f%z "$full")
  if [ "$size" -lt "$minb" ]; then fail "fs $rel" "size=$size < min=$minb"; return; fi
  if [ -n "$want" ] && ! grep -q "$want" "$full"; then
    fail "fs $rel" "missing substring: $want"; return
  fi
  ok "fs $rel ($size bytes)"
}

probe_alive() {
  local name="$1" url="$2"
  local code
  code=$(curl -sSk -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null) || code="000"
  if [ "$code" = "000" ]; then fail "$name" "$url -> no HTTP response"; return; fi
  ok "$name (HTTP $code)"
}

echo "Smoke ($MODE) against: $BASE"
echo "================================================"

# --- nginx vhost is alive (auth_request may 302 → /login, that's fine) ---
echo "Nginx vhost:"
probe_status "vhost / responds"           "/"                       "200 301 302"
probe_status "vhost /assets/ routes"      "/assets/css/app.css"     "200 301 302"
probe_status "vhost /src/ routes"         "/src/infra/index.js"     "200 301 302"
probe_status "vhost /login is reachable"  "/login"                  "200 301 302"

# --- Filesystem-level integrity (local mode only — sees actual deployed files) ---
if [ "$MODE" = "local" ]; then
  echo "------------------------------------------------"
  echo "Deployed files in $WEBROOT:"
  probe_file "index.html"            5000  "</html>"
  probe_file "assets/css/app.css"    1000  ""
  probe_file "src/infra/index.js"     200  "export"
  probe_file "src/domain/chat.js"     200  "export"
  probe_file "src/ui/skillsPanel.js"  200  "export"
  probe_file "src/ui/markdown.js"     200  "export"
  probe_file "src/ui/fileHelpers.js"  200  "export"
  probe_file "src/ui/messageActions.js" 100 "export"
  probe_file "src/ui/tts.js"          100  "export"
  probe_file "src/ui/searchHelpers.js"  200 "export"
  probe_file "src/ui/memoryPanel.js"    300 "export"
  probe_file "src/ui/demoCodes.js"      300 "export"

  # Sanity: deploy in /var/www/chat matches openclaw-deploy/web (catches "forgot to sync")
  if diff -q /var/www/chat/index.html /home/nikefd/openclaw-deploy/web/index.html >/dev/null 2>&1; then
    ok "deploy index.html matches openclaw-deploy"
  else
    fail "deploy out of sync" "/var/www/chat/index.html != /home/nikefd/openclaw-deploy/web/index.html"
  fi
fi

# --- Local Node services ---
if [ "$MODE" = "local" ]; then
  echo "------------------------------------------------"
  echo "Local Node services (port alive):"
  probe_alive "file-api    7682" "http://127.0.0.1:7682/"
  probe_alive "auth-api    7683" "http://127.0.0.1:7683/"
  probe_alive "finance-api 7684" "http://127.0.0.1:7684/"
  probe_alive "agents-api  7685" "http://127.0.0.1:7685/"
  probe_alive "usage-api   7686" "http://127.0.0.1:7686/api/usage"
  probe_alive "perf-api    7687" "http://127.0.0.1:7687/"
fi

echo "================================================"
if [ "$FAIL" -gt 0 ]; then
  printf "Smoke: %d pass, " "$PASS"; c_red "$FAIL fail"; echo
  printf "Failed: %s\n" "${FAILED_NAMES[*]}"
  exit 1
fi
printf "Smoke: %d pass, 0 fail\n" "$PASS"
