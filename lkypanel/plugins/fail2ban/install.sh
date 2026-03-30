#!/usr/bin/env bash
set -euo pipefail
# Fail2ban install script

FLAG_DIR="${FLAG_DIR:-/usr/local/lkypanel/plugins}"
FLAG_FILE="${FLAG_FILE:-$FLAG_DIR/fail2ban}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"
APP_ROOT="/usr/local/lkypanel"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ -f "$FLAG_FILE" ]]; then
    echo "Plugin already installed.[200]" >> "$LOG_FILE"
    exit 0
fi

# 1. Install fail2ban
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y fail2ban
else
    sudo yum install -y fail2ban
fi

# 2. Deploy hardening configs
sudo cp "$APP_ROOT/hardening/fail2ban-lkypanel.conf" "/etc/fail2ban/jail.d/lkypanel.conf"
sudo cp "$APP_ROOT/hardening/lkypanel.filter" "/etc/fail2ban/filter.d/lkypanel.conf"

# 3. Enable and start fail2ban
sudo systemctl enable --now fail2ban
sudo systemctl restart fail2ban

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
