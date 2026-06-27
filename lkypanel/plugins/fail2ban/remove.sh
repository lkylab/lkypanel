#!/usr/bin/env bash
set -euo pipefail
# Fail2ban remove script — full implementation in Task 2
FLAG_FILE="${FLAG_FILE:-/usr/local/lkypanel/plugins/fail2ban}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ ! -f "$FLAG_FILE" ]]; then
    echo "Plugin not installed.[200]" >> "$LOG_FILE"
    exit 0
fi

sudo systemctl disable --now fail2ban || true

if command -v apt-get &>/dev/null; then
    sudo apt-get remove -y fail2ban
else
    sudo yum remove -y fail2ban
fi

rm -f "$FLAG_FILE"
echo "Plugin removed.[200]" >> "$LOG_FILE"
