#!/usr/bin/env bash
set -euo pipefail
# Postfix install script — full implementation in Task 2
FLAG_DIR="${FLAG_DIR:-/usr/local/lkypanel/plugins}"
FLAG_FILE="${FLAG_FILE:-$FLAG_DIR/postfix}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

exec 2>> "$LOG_FILE"
set -x

trap 'echo "Plugin operation failed.[404]"' ERR

if [[ -f "$FLAG_FILE" ]]; then
    echo "Plugin already installed.[200]" >> "$LOG_FILE"
    exit 0
fi

if command -v apt-get &>/dev/null; then
    echo "postfix postfix/main_mailer_type string 'Internet Site'" | sudo debconf-set-selections
    echo "postfix postfix/mailname string $(hostname)" | sudo debconf-set-selections
    sudo apt-get install -y -q postfix mailutils dovecot-imapd dovecot-pop3d dovecot-lmtpd 2>> "$LOG_FILE"
else
    sudo yum install -y -q postfix dovecot 2>> "$LOG_FILE"
fi

sudo systemctl enable --now postfix
sudo systemctl enable --now dovecot 2>> "$LOG_FILE" || warn "Dovecot service failed to start (check if it is configured correctly)"

if command -v ufw &>/dev/null; then
    sudo ufw allow 25/tcp    || true
    sudo ufw allow 587/tcp   || true
    sudo ufw allow 143/tcp   || true
    sudo ufw allow 993/tcp   || true
    sudo ufw allow 110/tcp   || true
    sudo ufw allow 995/tcp   || true
elif command -v firewall-cmd &>/dev/null; then
    for port in 25 587 143 993 110 995; do
        sudo firewall-cmd --permanent --add-port=$port/tcp 2>/dev/null || true
    done
    sudo firewall-cmd --reload 2>/dev/null || true
fi

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
