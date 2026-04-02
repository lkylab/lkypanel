#!/usr/bin/env bash
# =============================================================================
# LkyPanel Uninstaller
# Usage: sudo bash uninstall.sh
# =============================================================================
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Config ────────────────────────────────────────────────────────────────────
INSTALL_DIR="/usr/local/lkypanel"
SERVICE_DIR="/etc/systemd/system"
PANEL_USER="lkypanel"
LOG_DIR="/var/log/lkypanel"

# ── Root check ────────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root: sudo bash uninstall.sh"

echo -e "${RED}${BOLD}!!! WARNING: This will completely remove LkyPanel and all its data !!!${NC}"
echo -e "This includes the database, SSL certificates, and configuration."
read -p "Are you sure you want to proceed? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    die "Uninstallation cancelled."
fi

# ── Stop and Remove Services ──────────────────────────────────────────────────
info "Stopping and removing systemd services..."
for SERVICE in lky-admin lky-user; do
    if systemctl is-active --quiet "$SERVICE"; then
        systemctl stop "$SERVICE" || true
    fi
    if [[ -f "$SERVICE_DIR/$SERVICE.service" ]]; then
        systemctl disable "$SERVICE" || true
        rm -f "$SERVICE_DIR/$SERVICE.service"
        success "Removed $SERVICE.service"
    fi
done
systemctl daemon-reload

# ── Remove Sudoers Hardening ──────────────────────────────────────────────────
info "Removing sudoers hardening..."
if [[ -f "/etc/sudoers.d/lkypanel" ]]; then
    rm -f "/etc/sudoers.d/lkypanel"
    success "Removed /etc/sudoers.d/lkypanel"
fi

# ── Remove CLI Symlink ────────────────────────────────────────────────────────
info "Removing CLI symlink..."
if [[ -L "/usr/local/bin/lky" ]]; then
    rm -f "/usr/local/bin/lky"
    success "Removed /usr/local/bin/lky"
fi

# ── Remove Directories ────────────────────────────────────────────────────────
info "Removing installation and log directories..."
if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
    success "Removed $INSTALL_DIR"
fi
if [[ -d "$LOG_DIR" ]]; then
    rm -rf "$LOG_DIR"
    success "Removed $LOG_DIR"
fi

# ── Remove System User ────────────────────────────────────────────────────────
info "Removing system user and group..."
if getent passwd "$PANEL_USER" >/dev/null; then
    userdel -f "$PANEL_USER" || true
    success "Removed user $PANEL_USER"
fi
if getent group "$PANEL_USER" >/dev/null; then
    groupdel "$PANEL_USER" || true
    success "Removed group $PANEL_USER"
fi

# ── Cleanup Firewall (Optional) ──────────────────────────────────────────────
info "Cleaning up firewall rules..."
if command -v ufw &>/dev/null; then
    ufw delete allow 2087/tcp >/dev/null 2>&1 || true
    ufw delete allow 2083/tcp >/dev/null 2>&1 || true
    success "UFW rules removed"
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --remove-port=2087/tcp >/dev/null 2>&1 || true
    firewall-cmd --permanent --remove-port=2083/tcp >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
    success "Firewalld rules removed"
fi

# ── Remove System Packages (Optional) ──────────────────────────────────────────
echo ""
echo -e "${YELLOW}${BOLD}Would you like to remove system packages installed by LkyPanel?${NC}"
echo -e "This includes: OpenLiteSpeed, LSPHP 8.3, Node.js 22, and Python 3.12."
warn "CAUTION: This may break other applications on this server!"
read -p "Remove system packages? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    info "Removing system packages..."
    if [[ -f /etc/debian_version ]]; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get purge -y openlitespeed lsphp83* nodejs python3.12* || true
        apt-get autoremove -y || true
        rm -rf /usr/local/lsws
    elif [[ -f /etc/redhat-release ]]; then
        yum remove -y openlitespeed lsphp83* nodejs python3.12* || true
        rm -rf /usr/local/lsws
    fi
    success "System packages removed"
fi

echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  LkyPanel has been uninstalled successfully!${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo ""
