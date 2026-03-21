#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="${DOMAIN:-zhangyangbin.com}"
OPENCLAW_PORT="${OPENCLAW_PORT:-18789}"
TTYD_PORT="${TTYD_PORT:-7681}"
FILE_API_PORT="${FILE_API_PORT:-7682}"

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

[ -f "$SCRIPT_DIR/.env" ] && source "$SCRIPT_DIR/.env"

# --- 1. System dependencies ---
echo -e "\n[1/8] System dependencies"
retry "sudo apt-get update -qq"
retry "sudo apt-get install -y -qq nginx curl jq ttyd apache2-utils"

# --- 2. Node / OpenClaw ---
echo -e "\n[2/8] Checking OpenClaw"
if ! command -v openclaw &>/dev/null; then
    echo "  Installing OpenClaw..."
    retry "npm install -g openclaw"
fi
echo "  OpenClaw: $(openclaw --version 2>/dev/null || openclaw version 2>/dev/null)"

# --- 3. systemd services ---
echo -e "\n[3/8] Configuring systemd user services"
SYSTEMD_DIR="$HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_DIR"

# OpenClaw gateway
[ -f "$SYSTEMD_DIR/openclaw-gateway.service" ] && \
    cp "$SYSTEMD_DIR/openclaw-gateway.service" "$SYSTEMD_DIR/openclaw-gateway.service.bak.$(date +%s)"
sed "s|\${OPENCLAW_PORT}|${OPENCLAW_PORT}|g" \
    "$SCRIPT_DIR/systemd/openclaw.service.template" \
    > "$SYSTEMD_DIR/openclaw-gateway.service"

# ttyd web terminal
cat > "$SYSTEMD_DIR/ttyd.service" << EOF
[Unit]
Description=ttyd Web Terminal
After=network.target
[Service]
ExecStart=/usr/bin/ttyd -p ${TTYD_PORT} -i 127.0.0.1 -b /terminal -W bash
Restart=always
RestartSec=3
[Install]
WantedBy=default.target
EOF

# File browser API
cat > "$SYSTEMD_DIR/file-api.service" << EOF
[Unit]
Description=File Browser API
After=network.target
[Service]
ExecStart=/usr/bin/node ${SCRIPT_DIR}/scripts/file-api-server.js
Restart=always
RestartSec=3
Environment=FILE_API_PORT=${FILE_API_PORT}
[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
retry "systemctl --user enable --now openclaw-gateway.service ttyd.service file-api.service"
sleep 2
echo "  ✓ OpenClaw gateway on 127.0.0.1:${OPENCLAW_PORT}"
echo "  ✓ ttyd on 127.0.0.1:${TTYD_PORT}"
echo "  ✓ File API on 127.0.0.1:${FILE_API_PORT}"

# --- 4. Chat UI ---
echo -e "\n[4/8] Deploying Chat UI"
sudo mkdir -p /var/www/chat
sudo cp "$SCRIPT_DIR/web/index.html" /var/www/chat/index.html
echo "  ✓ Chat UI → /var/www/chat/"

# --- 5. Basic Auth ---
echo -e "\n[5/8] HTTP Basic Auth"
if [ ! -f /etc/nginx/.htpasswd ]; then
    echo "  Creating .htpasswd — set your password:"
    sudo htpasswd -c /etc/nginx/.htpasswd "${HTTP_USER:-admin}"
else
    echo "  ✓ .htpasswd already exists"
fi

# --- 6. Nginx ---
echo -e "\n[6/8] Configuring Nginx"
NGINX_CONF="/etc/nginx/sites-available/openclaw.conf"
[ -f "$NGINX_CONF" ] && sudo cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%s)"

sed -e "s|\${DOMAIN}|${DOMAIN}|g" \
    -e "s|\${OPENCLAW_PORT}|${OPENCLAW_PORT}|g" \
    -e "s|\${TTYD_PORT}|${TTYD_PORT}|g" \
    -e "s|\${FILE_API_PORT}|${FILE_API_PORT}|g" \
    "$SCRIPT_DIR/nginx/openclaw.conf.template" | sudo tee "$NGINX_CONF" >/dev/null
sudo cp "$NGINX_CONF" /etc/nginx/sites-enabled/openclaw.conf
sudo rm -f /etc/nginx/sites-enabled/default

retry "sudo nginx -t"
retry "sudo systemctl enable --now nginx"
retry "sudo systemctl reload nginx"
echo "  ✓ Nginx → http://${DOMAIN}"

# --- 7. Healthcheck ---
echo -e "\n[7/8] Healthcheck"
sleep 1
echo -n "  Gateway:   "; curl -sf "http://127.0.0.1:${OPENCLAW_PORT}/" -o /dev/null && echo "✓" || echo "✗"
echo -n "  ttyd:      "; curl -sf "http://127.0.0.1:${TTYD_PORT}/terminal/" -o /dev/null && echo "✓" || echo "✗"
echo -n "  File API:  "; curl -sf "http://127.0.0.1:${FILE_API_PORT}/api/files/list" -o /dev/null && echo "✓" || echo "✗"
echo -n "  Nginx:     "; curl -sf -H "Host: ${DOMAIN}" "http://127.0.0.1:80/" -o /dev/null && echo "✓" || echo "✗"

# --- 8. Summary ---
echo -e "\n[8/8] Done!"
echo "========================================="
echo " ✓ OpenClaw gateway:  127.0.0.1:${OPENCLAW_PORT}"
echo " ✓ Web terminal:      127.0.0.1:${TTYD_PORT}"
echo " ✓ File browser API:  127.0.0.1:${FILE_API_PORT}"
echo " ✓ Nginx proxy:       http://${DOMAIN}"
echo " ✓ Chat UI:           http://${DOMAIN}/"
echo " ✓ Terminal:          http://${DOMAIN}/terminal/"
echo " ✓ Dashboard:         http://${DOMAIN}/dashboard/"
echo ""
echo " Next steps:"
echo "   - Point DNS A record for ${DOMAIN} → this server's public IP"
echo "   - Add HTTPS: sudo certbot --nginx -d ${DOMAIN}"
echo "   - Update Gateway token in web/index.html"
echo "========================================="
