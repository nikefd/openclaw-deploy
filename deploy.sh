#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="${DOMAIN:-zhangyangbin.com}"
OPENCLAW_PORT="${OPENCLAW_PORT:-18789}"

echo "========================================="
echo " OpenClaw Deploy — $DOMAIN"
echo "========================================="

retry() {
    local cmd="$*"
    echo "→ $cmd"
    if ! eval "$cmd"; then
        echo "⚠ Failed, retrying once..."
        sleep 2
        eval "$cmd"
    fi
}

# --- Load .env if present ---
[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"

# --- 1. System dependencies ---
echo -e "\n[1/6] System dependencies"
retry "sudo apt-get update -qq"
retry "sudo apt-get install -y -qq nginx curl jq"

# --- 2. Node / OpenClaw check ---
echo -e "\n[2/6] Checking OpenClaw"
if ! command -v openclaw &>/dev/null; then
    echo "OpenClaw not found. Installing via npm..."
    retry "npm install -g openclaw"
fi
echo "  OpenClaw: $(openclaw --version 2>/dev/null || openclaw version 2>/dev/null)"

# --- 3. systemd service (user) ---
echo -e "\n[3/6] Configuring systemd user service"
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

# Backup existing
[ -f "$SYSTEMD_DIR/openclaw-gateway.service" ] && \
    cp "$SYSTEMD_DIR/openclaw-gateway.service" "$SYSTEMD_DIR/openclaw-gateway.service.bak.$(date +%s)"

# Render template
sed "s|\${OPENCLAW_PORT}|${OPENCLAW_PORT}|g" \
    "$SCRIPT_DIR/systemd/openclaw.service.template" \
    > "$SYSTEMD_DIR/openclaw-gateway.service"

systemctl --user daemon-reload
retry "systemctl --user enable --now openclaw-gateway.service"
sleep 2
systemctl --user status openclaw-gateway.service --no-pager || true
echo "  ✓ OpenClaw gateway on 127.0.0.1:${OPENCLAW_PORT}"

# --- 4. Nginx ---
echo -e "\n[4/6] Configuring Nginx"
NGINX_CONF="/etc/nginx/sites-available/openclaw.conf"

# Backup existing
[ -f "$NGINX_CONF" ] && sudo cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%s)"

# Render template
sed -e "s|\${DOMAIN}|${DOMAIN}|g" \
    -e "s|\${OPENCLAW_PORT}|${OPENCLAW_PORT}|g" \
    "$SCRIPT_DIR/nginx/openclaw.conf.template" | sudo tee "$NGINX_CONF" >/dev/null

sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/openclaw.conf
# Remove default if it conflicts on port 80
sudo rm -f /etc/nginx/sites-enabled/default

echo "  Testing nginx config..."
retry "sudo nginx -t"
retry "sudo systemctl enable --now nginx"
retry "sudo systemctl reload nginx"
echo "  ✓ Nginx → http://${DOMAIN}"

# --- 5. Healthcheck ---
echo -e "\n[5/6] Running healthcheck"
sleep 1
echo -n "  Local probe: "
curl -sf "http://127.0.0.1:${OPENCLAW_PORT}/" -o /dev/null && echo "✓ OK" || echo "✗ FAIL"
echo -n "  Nginx probe (via localhost:80): "
curl -sf -H "Host: ${DOMAIN}" "http://127.0.0.1:80/" -o /dev/null && echo "✓ OK" || echo "✗ FAIL"

# --- 6. Summary ---
echo -e "\n[6/6] Done!"
echo "========================================="
echo " ✓ OpenClaw gateway:  127.0.0.1:${OPENCLAW_PORT}"
echo " ✓ Nginx reverse proxy: http://${DOMAIN}"
echo " ✓ systemd service:     openclaw-gateway (user)"
echo ""
echo " Next steps:"
echo "   - Point DNS A record for ${DOMAIN} → this server's public IP"
echo "   - (Optional) Add HTTPS: sudo certbot --nginx -d ${DOMAIN}"
echo "========================================="
