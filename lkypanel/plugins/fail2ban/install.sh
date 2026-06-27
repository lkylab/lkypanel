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
sudo tee "/etc/fail2ban/jail.d/lkypanel.conf" > /dev/null <<EOF
[lky-admin]
enabled = True
port = 2087
filter = lkypanel
logpath = /var/log/lkypanel/admin-error.log
maxretry = 3
findtime = 600
bantime = 3600

[lky-user]
enabled = True
port = 2083
filter = lkypanel
logpath = /var/log/lkypanel/user-error.log
maxretry = 3
findtime = 600
bantime = 3600
EOF

sudo tee "/etc/fail2ban/filter.d/lkypanel.conf" > /dev/null <<EOF
[Definition]
failregex = Failed login attempt for user '.*' from IP <ADDR>
ignoreregex =
EOF

# 3. Enable and start fail2ban
sudo systemctl enable --now fail2ban
sudo systemctl restart fail2ban

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
