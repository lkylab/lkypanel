#!/usr/bin/env bash
set -euo pipefail
# Pure-FTPd remove script — full implementation in Task 2
FLAG_FILE="${FLAG_FILE:-/usr/local/lkypanel/plugins/pureftpd}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ ! -f "$FLAG_FILE" ]]; then
    echo "Plugin not installed.[200]" >> "$LOG_FILE"
    exit 0
fi

systemctl disable --now pure-ftpd || true

if command -v apt-get &>/dev/null; then
    apt-get remove -y pure-ftpd
else
    yum remove -y pure-ftpd
fi

if command -v ufw &>/dev/null; then
    ufw delete allow 21/tcp
    ufw delete allow 20/tcp
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --remove-port=21/tcp
    firewall-cmd --permanent --remove-port=20/tcp
    firewall-cmd --reload
fi

rm -f "$FLAG_FILE"
echo "Plugin removed.[200]" >> "$LOG_FILE"
