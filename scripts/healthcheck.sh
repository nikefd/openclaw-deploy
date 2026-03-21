#!/usr/bin/env bash
# Healthcheck script for OpenClaw deployment
set -euo pipefail

DOMAIN="${DOMAIN:-zhangyangbin.com}"
PORT="${OPENCLAW_PORT:-18789}"
ERRORS=0

check() {
    local label="$1" cmd="$2"
    printf "  %-30s " "$label"
    if eval "$cmd" &>/dev/null; then
        echo "✓ OK"
    else
        echo "✗ FAIL"
        ((ERRORS++))
    fi
}

echo "OpenClaw Healthcheck"
echo "--------------------"
check "Gateway (localhost:$PORT)" "curl -sf http://127.0.0.1:$PORT/"
check "Nginx (port 80)" "curl -sf -H 'Host: $DOMAIN' http://127.0.0.1:80/"
check "systemd service" "systemctl --user is-active openclaw-gateway.service"
check "Nginx service" "systemctl is-active nginx"
check "Nginx config" "sudo nginx -t"

echo ""
if [ "$ERRORS" -eq 0 ]; then
    echo "All checks passed ✓"
else
    echo "$ERRORS check(s) failed ✗"
    exit 1
fi
