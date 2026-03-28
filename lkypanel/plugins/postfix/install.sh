#!/usr/bin/env bash
set -euo pipefail
# Postfix install script — full implementation in Task 2
FLAG_DIR="${FLAG_DIR:-/usr/local/lkypanel/plugins}"
FLAG_FILE="${FLAG_FILE:-$FLAG_DIR/postfix}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ -f "$FLAG_FILE" ]]; then
    echo "Plugin already installed.[200]" >> "$LOG_FILE"
    exit 0
fi

if command -v apt-get &>/dev/null; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y postfix mailutils
else
    yum install -y postfix
fi

systemctl enable --now postfix

if command -v ufw &>/dev/null; then
    ufw allow 25/tcp
    ufw allow 587/tcp
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port=25/tcp
    firewall-cmd --permanent --add-port=587/tcp
    firewall-cmd --reload
fi

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
