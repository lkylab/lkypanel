#!/usr/bin/env bash
set -euo pipefail
# Redis remove script — full implementation in Task 2
FLAG_FILE="${FLAG_FILE:-/usr/local/lkypanel/plugins/redis}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ ! -f "$FLAG_FILE" ]]; then
    echo "Plugin not installed.[200]" >> "$LOG_FILE"
    exit 0
fi

systemctl disable --now redis || true

if command -v apt-get &>/dev/null; then
    apt-get remove -y redis-server
else
    yum remove -y redis
fi

rm -f "$FLAG_FILE"
echo "Plugin removed.[200]" >> "$LOG_FILE"
