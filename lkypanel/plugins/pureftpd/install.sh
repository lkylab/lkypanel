#!/usr/bin/env bash
set -euo pipefail
# Pure-FTPd install script — full implementation in Task 2
FLAG_DIR="${FLAG_DIR:-/usr/local/lkypanel/plugins}"
FLAG_FILE="${FLAG_FILE:-$FLAG_DIR/pureftpd}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ -f "$FLAG_FILE" ]]; then
    echo "Plugin already installed.[200]" >> "$LOG_FILE"
    exit 0
fi

if command -v apt-get &>/dev/null; then PKG_MGR="apt"; else PKG_MGR="yum"; fi

if [[ "$PKG_MGR" == "apt" ]]; then
    apt-get install -y pure-ftpd
else
    yum install -y pure-ftpd
fi

systemctl enable --now pure-ftpd

if command -v ufw &>/dev/null; then
    ufw allow 21/tcp
    ufw allow 20/tcp
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port=21/tcp
    firewall-cmd --permanent --add-port=20/tcp
    firewall-cmd --reload
fi

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
