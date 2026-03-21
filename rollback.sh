#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo " OpenClaw Rollback"
echo "========================================="

# Restore Nginx
NGINX_BAK=$(ls -t /etc/nginx/sites-available/openclaw.conf.bak.* 2>/dev/null | head -1)
if [ -n "$NGINX_BAK" ]; then
    echo "→ Restoring Nginx config from $NGINX_BAK"
    sudo cp "$NGINX_BAK" /etc/nginx/sites-available/openclaw.conf
    sudo nginx -t && sudo systemctl reload nginx
    echo "  ✓ Nginx restored"
else
    echo "  No Nginx backup found, removing config"
    sudo rm -f /etc/nginx/sites-enabled/openclaw.conf
    sudo systemctl reload nginx
fi

# Restore systemd
SYSTEMD_DIR="$HOME/.config/systemd/user"
SVC_BAK=$(ls -t "$SYSTEMD_DIR"/openclaw-gateway.service.bak.* 2>/dev/null | head -1)
if [ -n "$SVC_BAK" ]; then
    echo "→ Restoring systemd service from $SVC_BAK"
    cp "$SVC_BAK" "$SYSTEMD_DIR/openclaw-gateway.service"
    systemctl --user daemon-reload
    systemctl --user restart openclaw-gateway.service
    echo "  ✓ systemd service restored"
else
    echo "  No systemd backup found, skipping"
fi

echo "========================================="
echo " Rollback complete"
echo "========================================="
