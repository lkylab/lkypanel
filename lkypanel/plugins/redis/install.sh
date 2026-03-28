#!/usr/bin/env bash
set -euo pipefail
# Redis install script — full implementation in Task 2
FLAG_DIR="${FLAG_DIR:-/usr/local/lkypanel/plugins}"
FLAG_FILE="${FLAG_FILE:-$FLAG_DIR/redis}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

exec 2>> "$LOG_FILE"
set -x

trap 'echo "Plugin operation failed.[404]"' ERR

if [[ -f "$FLAG_FILE" ]]; then
    echo "Plugin already installed.[200]" >> "$LOG_FILE"
    exit 0
fi

if command -v apt-get &>/dev/null; then PKG_MGR="apt"; else PKG_MGR="yum"; fi

if [[ "$PKG_MGR" == "apt" ]]; then
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y redis-server 2>> "$LOG_FILE"
    SERVICE_NAME="redis-server"
else
    sudo yum install -y redis 2>> "$LOG_FILE"
    SERVICE_NAME="redis"
fi

sudo systemctl enable --now "$SERVICE_NAME" 2>> "$LOG_FILE" || true

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
