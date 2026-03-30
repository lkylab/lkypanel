#!/usr/bin/env bash
set -euo pipefail

# phpMyAdmin install script (CyberPanel-style, No Apache)
FLAG_DIR="${FLAG_DIR:-/usr/local/lkypanel/plugins}"
FLAG_FILE="${FLAG_FILE:-$FLAG_DIR/phpmyadmin}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"
INSTALL_DIR="/usr/local/lkypanel/phpmyadmin"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ -f "$FLAG_FILE" ]]; then
    echo "Plugin already installed.[200]" >> "$LOG_FILE"
    exit 0
fi

echo "[INFO] Starting phpMyAdmin installation (CyberPanel-style)..."

# 1. Stop and disable Apache if it exists
if command -v apache2 &>/dev/null; then
    echo "[INFO] Stopping and disabling Apache2 to prevent port conflicts..."
    sudo systemctl stop apache2 || true
    sudo systemctl disable apache2 || true
fi

# 2. Install dependencies (lsphp extensions)
echo "[INFO] Installing PHP extensions for OpenLiteSpeed..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq lsphp83-mysql lsphp83-common lsphp83-gd lsphp83-mbstring lsphp83-zip lsphp83-curl lsphp83-xml
else
    sudo yum install -y -q lsphp83-mysql lsphp83-common lsphp83-gd lsphp83-mbstring lsphp83-zip lsphp83-curl lsphp83-xml
fi

# 3. Download phpMyAdmin
echo "[INFO] Downloading phpMyAdmin source..."
sudo mkdir -p "$INSTALL_DIR"
cd /tmp
wget -q https://www.phpmyadmin.net/downloads/phpMyAdmin-latest-all-languages.tar.gz
tar -xzf phpMyAdmin-latest-all-languages.tar.gz
sudo mv phpMyAdmin-*-all-languages/* "$INSTALL_DIR/"
rm -rf phpMyAdmin-*-all-languages phpMyAdmin-latest-all-languages.tar.gz

# 4. Configure phpMyAdmin
echo "[INFO] Generating config.inc.php..."
BLOWFISH_SECRET=$(openssl rand -base64 32)
sudo tee "$INSTALL_DIR/config.inc.php" > /dev/null <<EOF
<?php
\$cfg['blowfish_secret'] = '${BLOWFISH_SECRET}';
\$i = 0;
\$i++;
\$cfg['Servers'][\$i]['auth_type'] = 'cookie';
\$cfg['Servers'][\$i]['host'] = 'localhost';
\$cfg['Servers'][\$i]['compress'] = false;
\$cfg['Servers'][\$i]['AllowNoPassword'] = false;
\$cfg['UploadDir'] = '';
\$cfg['SaveDir'] = '';
EOF

# 5. Set permissions
sudo chown -R lkypanel:lkypanel "$INSTALL_DIR"
sudo chmod -R 755 "$INSTALL_DIR"

# 6. Mark as installed
mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
