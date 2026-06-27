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
    sudo apt-get install -y pure-ftpd
else
    sudo yum install -y pure-ftpd
fi

sudo systemctl enable --now pure-ftpd

if command -v ufw &>/dev/null; then
    sudo ufw allow 21/tcp
    sudo ufw allow 20/tcp
elif command -v firewall-cmd &>/dev/null; then
    sudo firewall-cmd --permanent --add-port=21/tcp
    sudo firewall-cmd --permanent --add-port=20/tcp
    sudo firewall-cmd --reload
fi

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
