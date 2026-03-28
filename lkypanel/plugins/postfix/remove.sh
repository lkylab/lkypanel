#!/usr/bin/env bash
set -euo pipefail
# Postfix remove script — full implementation in Task 2
FLAG_FILE="${FLAG_FILE:-/usr/local/lkypanel/plugins/postfix}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ ! -f "$FLAG_FILE" ]]; then
    echo "Plugin not installed.[200]" >> "$LOG_FILE"
    exit 0
fi

sudo systemctl disable --now postfix || true

if command -v apt-get &>/dev/null; then
    sudo apt-get remove -y postfix mailutils
else
    sudo yum remove -y postfix
fi

if command -v ufw &>/dev/null; then
    sudo ufw delete allow 25/tcp
    sudo ufw delete allow 587/tcp
elif command -v firewall-cmd &>/dev/null; then
    sudo firewall-cmd --permanent --remove-port=25/tcp
    sudo firewall-cmd --permanent --remove-port=587/tcp
    sudo firewall-cmd --reload
fi

rm -f "$FLAG_FILE"
echo "Plugin removed.[200]" >> "$LOG_FILE"
