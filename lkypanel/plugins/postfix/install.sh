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
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y postfix dovecot-imapd dovecot-pop3d dovecot-lmtpd mailutils
else
    sudo yum install -y postfix dovecot
fi

sudo systemctl enable --now postfix

if command -v ufw &>/dev/null; then
    sudo ufw allow 25/tcp
    sudo ufw allow 587/tcp
    sudo ufw allow 143/tcp
    sudo ufw allow 993/tcp
    sudo ufw allow 110/tcp
    sudo ufw allow 995/tcp
elif command -v firewall-cmd &>/dev/null; then
    sudo firewall-cmd --permanent --add-port={25,587,143,993,110,995}/tcp
    sudo firewall-cmd --reload
fi

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
