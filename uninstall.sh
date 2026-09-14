#!/usr/bin/env bash
# =============================================================================
# W3Panel v2 Uninstaller
# Usage: sudo bash uninstall.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }

INSTALL_DIR="/usr/local/w3panel"
ETC_DIR="/etc/w3panel"
VAR_DIR="/var/lib/w3panel"
LOG_DIR="/var/log/w3panel"
SERVICE_DIR="/etc/systemd/system"
PANEL_USER="w3panel"

[[ $EUID -eq 0 ]] || { echo "Run as root: sudo bash uninstall.sh"; exit 1; }

echo -e "${BOLD}"
echo "  W3Panel v2 Uninstaller"
echo -e "${NC}"

# Stop services
info "Stopping services..."
systemctl stop w3panel-admin w3panel-user 2>/dev/null || true
systemctl disable w3panel-admin w3panel-user 2>/dev/null || true

# Remove service files
info "Removing systemd services..."
rm -f "$SERVICE_DIR/w3panel-admin.service" "$SERVICE_DIR/w3panel-user.service"
systemctl daemon-reload

# Remove files
info "Removing installation files..."
rm -rf "$INSTALL_DIR" "$ETC_DIR" "$VAR_DIR" "$LOG_DIR"

# Remove system user
info "Removing system user..."
if id "$PANEL_USER" &>/dev/null; then
    userdel -r "$PANEL_USER" 2>/dev/null || true
fi

# Remove sudoers
info "Removing sudoers config..."
rm -f "/etc/sudoers.d/w3panel"

# Remove firewall rules
info "Removing firewall rules..."
if command -v ufw &>/dev/null; then
    ufw delete allow 2087/tcp 2>/dev/null || true
    ufw delete allow 2083/tcp 2>/dev/null || true
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --remove-port=2087/tcp 2>/dev/null || true
    firewall-cmd --permanent --remove-port=2083/tcp 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}${BOLD}W3Panel v2 uninstalled successfully!${NC}"
echo ""